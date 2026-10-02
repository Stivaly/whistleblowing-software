"""
Extractor del corpus normativo desde LeyChile (BCN).

Dos fuentes, mismo esquema de salida (1 fragmento por artículo):

  xml   Servicio oficial documentado: obtxml?opt=7&idNorma=<id>. Entrega SIEMPRE
        la última versión vigente. Es la fuente por defecto.
  json  API que usa el sitio bcn.cl/leychile: get_norma_json?idNorma=<id>[&idVersion=AAAA-MM-DD].
        Permite pedir una versión concreta (incluidas las de vigencia diferida)
        y trae notas que indican qué ley modificó cada artículo. No está
        documentada como servicio público: se usa solo donde el XML no basta.

Flujo por entrada de leyes.json:
  1. Descargar (con reintentos y pausa de cortesía); copia cruda en salida/fuentes/.
  2. Parsear y aplanar la jerarquía -> fragmentos (artículos largos se parten).
  3. Clasificar cada artículo: sustantivo (se embebe) o modificatorio /
     promulgatorio (se guarda para trazabilidad, no se embebe).
  4. Calcular la vigencia según la política de la entrada (ver "vigencia" abajo).
  5. Upsert en MongoDB conservando historial; respaldo JSON en salida/.

Claves de leyes.json por entrada:
  nombre, idNorma | idLey, categoria[], prioridad, activa, verificado
  fuente            "xml" (defecto) | "json"
  version           (json) fecha AAAA-MM-DD de la versión a pedir
  clave             identificador único de la entrada en el corpus (defecto: idNorma).
                    Obligatoria si la misma norma aparece en más de una entrada.
  vigencia          "bcn" (defecto: vigente si la BCN la da por vigente)
                    | "anticipada" (vigente en el corpus aunque la BCN la difiera;
                      queda vigencia_anticipada=true hasta la fecha de inicio)
                    | "historica" (contexto: vigente=false)
  solo_modificados_por  (json) idNorma de una ley: extraer solo los artículos que
                    esa ley modificó o creó (según las notas de la BCN)
  origen            texto libre: por qué está esta entrada (p. ej. "Ley 21.643")
  articulos_modificatorios / articulos_sustantivos: listas de números de
                    artículo para corregir a mano la clasificación automática

Uso:
  python3 extraer_bcn.py                         # entradas activas de leyes.json
  python3 extraer_bcn.py --normas 1984 21643     # solo esas (idNorma, idLey, clave o nombre)
  python3 extraer_bcn.py --verificar idLey=21643 idNorma=1984   # solo metadatos
  python3 extraer_bcn.py --dry-run               # no escribe en Mongo
  python3 extraer_bcn.py --desde-cache           # usa salida/fuentes/ en vez de descargar

Variables de entorno:
  MONGODB_URI   p. ej. mongodb+srv://user:pass@cluster.mongodb.net/kerna
  (sin MONGODB_URI escribe solo los JSON locales en ./salida/)
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

URL_XML = "https://www.leychile.cl/Consulta/obtxml?opt=7"
URL_JSON = "https://nuevo.leychile.cl/servicios/Navegar/get_norma_json"
NS_RE = re.compile(r"\{.*?\}")  # el XML viene con namespace; lo ignoramos
DIR = Path(__file__).parent
SALIDA = DIR / "salida"
FUENTES = SALIDA / "fuentes"
# Sin User-Agent identificable el servicio responde 401.
USER_AGENT = "Mozilla/5.0 (compatible; KernaAI-CorpusBot/1.0; proyecto academico; contacto: admin@kerna.ai)"
PAUSA_SEGUNDOS = 5  # cortesía con el servicio de la BCN
# El servicio responde 429 tras ~12 descargas seguidas (observado 2026-10-02).
REINTENTOS = 4
ESPERA_429 = 60  # segundos base si no viene Retry-After
# ~1.500 tokens a ~3.5 caracteres/token (español): sobre esto se parte por inciso.
MAX_CHARS_FRAGMENTO = 5000
# Texto de un artículo real: "Artículo 1°.-", "ART. 2.", '"Artículo 3' (no "ARTICULOS ...").
_ENCABEZADO_ART = re.compile(r"^\W*(art[íi]culo|art\.)(?!s)", re.IGNORECASE)
# Artículo cuyo contenido es una orden de modificar otra norma.
_MODIFICATORIO = re.compile(
    r"^\W*(art[íi]culo|art\.)\s*[\w°º]+(\s+(bis|ter|qu[áa]ter|transitorio))?\s*[°º]?\s*\.?-?\s*"
    r"(introd[úu]c[ea]n?se|modif[íi]c[ae]n?se|reempl[áa]z[ae]n?se|sustit[úu]y[ea]n?se|"
    r"agr[ée]g[ae]n?se|incorp[óo]r[ae]n?se|interc[áa]l[ae]n?se|supr[íi]m[ea]n?se|"
    r"der[óo]g[ae]n?se|elim[íi]n[ae]n?se)\b", re.IGNORECASE)
_PROMULGATORIO = re.compile(r"apru[ée]base\s+la\s+siguiente\s+ley", re.IGNORECASE)
_DEROGADO_TXT = re.compile(r"^\W*(art[íi]culo|art\.)\s*[^.]{0,25}\.?-?\s*(derogado|suprimido)\.?\s*$",
                           re.IGNORECASE)

log = logging.getLogger("extraer_bcn")


# ----------------------------------------------------------------- utilidades
def _tag(el) -> str:
    return NS_RE.sub("", el.tag)


def _hijo(el, nombre: str):
    return next((c for c in el if _tag(c) == nombre), None)


def _slug(s: str) -> str:
    # "ñ" se conserva distinguible: los artículos 183 N y 183 Ñ coexisten.
    s = unicodedata.normalize("NFD", s.lower().replace("ñ", "nn"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _texto_plano(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _normalizar_incisos(bruto: str) -> str:
    """Une líneas cortadas y deja los incisos separados por línea en blanco."""
    incisos = (" ".join(b.split()) for b in re.split(r"\n\s*\n", bruto))
    return "\n\n".join(i for i in incisos if i)


def _texto_incisos(el) -> str:
    # BCN corta líneas a ~60 columnas y separa incisos con línea en blanco.
    return _normalizar_incisos("".join(el.itertext())) if el is not None else ""


_NOTA_HTML = re.compile(r'<span class="n"[^>]*>.*?</span>', re.DOTALL)


def _texto_html(fragmento_html: str) -> str:
    """HTML de la API JSON -> texto. Las notas marginales de la BCN ("Ley 21719
    Art. primero N° 2) D.O. ...") vienen como <span class="n"> insertas incluso a
    mitad de palabra: se eliminan. Cada <div class="p"> es un inciso."""
    s = _NOTA_HTML.sub("", fragmento_html)
    s = re.sub(r"</div>|<br\s*/?>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return _normalizar_incisos(html.unescape(s).replace("\xa0", " "))


def _sha(s: str | bytes) -> str:
    return hashlib.sha256(s if isinstance(s, bytes) else s.encode()).hexdigest()


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _es_si(valor: str, positivo: str) -> bool:
    """Atributos BCN: 'derogado'/'no derogado', 'transitorio'/'no transitorio'."""
    return valor.strip().lower() == positivo


def _partir(texto: str, limite: int = MAX_CHARS_FRAGMENTO) -> list[str]:
    if len(texto) <= limite:
        return [texto]
    trozos = []
    for inciso in texto.split("\n\n"):
        if len(inciso) <= limite:
            trozos.append(inciso)
            continue
        # Inciso único demasiado largo: cortar por oraciones.
        frase_actual = ""
        for frase in re.split(r"(?<=[.;:])\s+", inciso):
            if frase_actual and len(frase_actual) + 1 + len(frase) > limite:
                trozos.append(frase_actual)
                frase_actual = frase
            else:
                frase_actual = f"{frase_actual} {frase}" if frase_actual else frase
        if frase_actual:
            trozos.append(frase_actual)
    partes, actual = [], ""
    for inciso in trozos:
        if actual and len(actual) + 2 + len(inciso) > limite:
            partes.append(actual)
            actual = inciso
        else:
            actual = f"{actual}\n\n{inciso}" if actual else inciso
    if actual:
        partes.append(actual)
    return partes


def clave_de(cfg: dict) -> str:
    return str(cfg.get("clave") or cfg.get("idNorma") or f"ley{cfg['idLey']}")


def fuente_de(cfg: dict) -> str:
    return cfg.get("fuente", "xml")


# ------------------------------------------------------------------- descarga
def url_norma(cfg: dict) -> str:
    if fuente_de(cfg) == "json":
        if "idNorma" not in cfg:
            raise ValueError("la fuente json requiere idNorma")
        url = f"{URL_JSON}?idNorma={cfg['idNorma']}"
        return url + (f"&idVersion={cfg['version']}" if cfg.get("version") else "")
    if "idNorma" in cfg:
        return f"{URL_XML}&idNorma={cfg['idNorma']}"
    return f"{URL_XML}&idLey={cfg['idLey']}"


def _validar_respuesta(datos: bytes, cfg: dict):
    if fuente_de(cfg) == "json":
        if not datos.lstrip().startswith(b"{") or b'"estructura"' not in datos:
            raise ValueError("respuesta JSON inesperada (¿la API de LeyChile cambió?)")
    elif b"<Norma" not in datos[:2000]:
        raise ValueError("respuesta sin <Norma> (¿página de error o norma inexistente?)")


def descargar(cfg: dict) -> bytes:
    url = url_norma(cfg)
    ultimo = None
    for intento in range(1, REINTENTOS + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://www.bcn.cl/leychile/"})
            with urllib.request.urlopen(req, timeout=180) as r:
                datos = r.read()
            _validar_respuesta(datos, cfg)
            return datos
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            ultimo = e
            espera = PAUSA_SEGUNDOS * intento * 2
            if isinstance(e, urllib.error.HTTPError):
                if e.code == 404:
                    break
                if e.code == 429:
                    ra = e.headers.get("Retry-After", "")
                    espera = int(ra) if ra.isdigit() else ESPERA_429 * intento
            if intento == REINTENTOS:
                break
            log.warning("descarga fallida (%s/%s) %s: %s — reintento en %ss",
                        intento, REINTENTOS, url, e, espera)
            time.sleep(espera)
    raise RuntimeError(f"no se pudo descargar {url}: {ultimo}")


def ruta_cache(cfg: dict, base: Path = FUENTES) -> Path:
    return base / f"{_slug(clave_de(cfg))}.{fuente_de(cfg)}"


# ------------------------------------------------------- armado de fragmentos
class _Armador:
    """Convierte artículos (ya extraídos de XML o JSON) en fragmentos del corpus."""

    def __init__(self, cfg: dict, meta: dict):
        self.cfg, self.meta = cfg, meta
        self.prefijo = _slug(clave_de(cfg))
        self.fragmentos: list[dict] = []
        self.ids: set[str] = set()
        self.ahora = _ahora()
        forz_mod = {_slug(str(a)) for a in cfg.get("articulos_modificatorios", [])}
        forz_sus = {_slug(str(a)) for a in cfg.get("articulos_sustantivos", [])}
        self.forzados = {**{a: "modificatoria" for a in forz_mod},
                         **{a: "sustantiva" for a in forz_sus}}

    def _id_unico(self, base: str, contexto: list[str]) -> str:
        if base not in self.ids:
            return base
        # Colisión (p. ej. doble articulado que repite numeración): desambiguar
        # con el contexto jerárquico y, en último caso, con un ordinal estable.
        cand = f"{base}--{_slug('-'.join(contexto))[:60]}"
        n = 2
        while cand in self.ids:
            cand = f"{base}--{n}"
            n += 1
        log.debug("id repetido %s -> %s", base, cand)
        return cand

    def _clasificar(self, num: str, texto: str, contiene_ley: bool) -> str:
        forzado = self.forzados.get(_slug(num))
        if forzado:
            return forzado
        if contiene_ley and _PROMULGATORIO.search(texto[:300]):
            return "promulgatoria"  # "Artículo Primero.- Apruébase la siguiente ley:"
        if _MODIFICATORIO.match(texto):
            return "modificatoria"
        return "sustantiva"

    def articulo(self, *, num: str, texto: str, ruta: list[str], transitorio: bool,
                 derogado: bool, fecha_version: str, id_parte: str,
                 contiene_ley: bool = False, modificado_por: list[str] | None = None):
        m = self.meta
        etiqueta = f"Artículo {num}" + (" transitorio" if transitorio else "")
        jerarquia = ruta + [etiqueta]
        derogado = derogado or bool(_DEROGADO_TXT.match(texto))
        tipo_contenido = self._clasificar(num, texto, contiene_ley)
        vigente = m["vigente"] and not derogado
        base = f"{self.prefijo}-art-{'t-' if transitorio else ''}{_slug(num)}"
        art_id = self._id_unico(base, ruta)
        self.ids.add(art_id)
        partes = _partir(texto)
        for i, parte in enumerate(partes, 1):
            frag_id = art_id if len(partes) == 1 else f"{art_id}-p{i}"
            marca = "" if len(partes) == 1 else f" (parte {i}/{len(partes)})"
            self.fragmentos.append({
                "_id": frag_id,
                "clave_corpus": m["clave"],
                "id_norma": m["id_norma"],
                "id_parte_bcn": str(id_parte or ""),
                "norma": m["nombre"],
                "tipo_numero": m["referencia"],
                "articulo": num + (" transitorio" if transitorio else ""),
                "parte": f"{i}/{len(partes)}" if len(partes) > 1 else "",
                "jerarquia": jerarquia,
                "texto": parte,
                "materias": m["materias"],
                "categorias": m["categorias"],
                "tipo_contenido": tipo_contenido,
                "transitorio": transitorio,
                "derogado": derogado,
                "modificado_por": modificado_por or [],
                "origen": m["origen"],
                "fecha_version": fecha_version or m["fecha_version"],
                "version_norma": m["version"],
                "vigencia_desde": m["vigencia_desde"],
                "vigencia_hasta": m["vigencia_hasta"],
                "vigencia_anticipada": m["vigencia_anticipada"],
                "vigente": vigente,
                "url_fuente": m["url_fuente"],
                "hash_texto": _sha(parte),
                # ---- CAMPO QUE SE TRANSFORMA EN EMBEDDING ----
                "texto_embedding": (
                    f"{m['referencia']} — {m['nombre']}. "
                    f"{' > '.join(jerarquia)}{marca}. {parte}"
                ),
                # Solo lo sustantivo va al índice vectorial.
                "estado_embedding": "pendiente" if tipo_contenido == "sustantiva" else "no_aplica",
                "actualizado_en": self.ahora,
            })


def _politica_vigencia(cfg: dict, desde: str, hasta: str, vigente_bcn: bool,
                       hoy: date | None = None) -> tuple[bool, bool]:
    """-> (vigente_en_corpus, vigencia_anticipada)."""
    hoy_s = (hoy or date.today()).isoformat()
    politica = cfg.get("vigencia", "bcn")
    if politica == "historica":
        return False, False
    if politica == "anticipada":
        return True, bool(desde) and hoy_s < desde
    if politica != "bcn":
        raise ValueError(f"vigencia desconocida: {politica}")
    if desde and hoy_s < desde:
        return False, False  # diferida y sin decisión de anticiparla
    if hasta and hoy_s > hasta:
        return False, False
    return vigente_bcn, False


def _doc_norma(cfg: dict, m: dict, crudo: bytes, total: int, articulos: int) -> dict:
    return {
        "_id": m["clave"],
        "clave": m["clave"],
        "id_norma": m["id_norma"],
        "nombre_corto": m["nombre"],
        "referencia": m["referencia"],
        "tipo": m["tipo"], "numero": m["numero"], "titulo": m["titulo"],
        "organismos": m["organismos"], "materias": m["materias"],
        "categorias": m["categorias"],
        "fuente": fuente_de(cfg),
        "url_descarga": url_norma(cfg),
        "fecha_version": m["fecha_version"],
        "version": m["version"],
        "vigencia_desde": m["vigencia_desde"], "vigencia_hasta": m["vigencia_hasta"],
        "politica_vigencia": cfg.get("vigencia", "bcn"),
        "vigente": m["vigente"], "vigencia_anticipada": m["vigencia_anticipada"],
        "fecha_publicacion": m["fecha_publicacion"],
        "derogado": m["derogado"],
        "solo_modificados_por": cfg.get("solo_modificados_por"),
        "origen": m["origen"],
        "url_fuente": m["url_fuente"],
        "hash_fuente": _sha(crudo),
        "total_fragmentos": total,
        "total_articulos": articulos,
        "extraido_en": _ahora(),
    }


def _meta_base(cfg: dict, id_norma: int, tipo: str, numero: str, titulo: str) -> dict:
    nombre = cfg.get("nombre") or titulo.title()
    # "Ley 20393", "Decreto con Fuerza de Ley 1"; los códigos traen Numero="PENAL".
    referencia = f"{tipo} {numero}" if numero.isdigit() else nombre
    version = cfg.get("version", "")
    url = f"https://www.bcn.cl/leychile/navegar?idNorma={id_norma}"
    return {"clave": clave_de(cfg), "id_norma": id_norma, "nombre": nombre,
            "referencia": referencia, "tipo": tipo, "numero": numero, "titulo": titulo,
            "categorias": cfg.get("categoria", []), "origen": cfg.get("origen", ""),
            "version": version,
            "url_fuente": url + (f"&idVersion={version}" if version else "")}


def _resultado(cfg, m, crudo, armador):
    frags = armador.fragmentos
    articulos = len({f["_id"].rsplit("-p", 1)[0] if f["parte"] else f["_id"] for f in frags})
    return _doc_norma(cfg, m, crudo, len(frags), articulos), frags


# ------------------------------------------------------------------ fuente XML
def parsear_xml(xml_bytes: bytes, cfg: dict, hoy: date | None = None) -> tuple[dict, list[dict]]:
    root = ET.fromstring(xml_bytes)
    norma_el = root if _tag(root) == "Norma" else next(
        (e for e in root.iter() if _tag(e) == "Norma"), None)
    if norma_el is None:
        raise ValueError("XML sin elemento <Norma>")

    attrs = norma_el.attrib
    id_norma = int(attrs.get("normaId") or attrs.get("idNorma") or cfg.get("idNorma", 0))
    ident = _hijo(norma_el, "Identificador")
    meta_el = _hijo(norma_el, "Metadatos")
    tipo = numero = titulo = ""
    organismos: list[str] = []
    materias: list[str] = []
    if ident is not None:
        tn = next((e for e in ident.iter() if _tag(e) == "TipoNumero"), None)
        if tn is not None:
            tipo = _texto_plano(_hijo(tn, "Tipo"))
            numero = _texto_plano(_hijo(tn, "Numero"))
        organismos = [v for e in ident.iter() if _tag(e) == "Organismo"
                      if (v := _texto_plano(e))]
    if meta_el is not None:
        titulo = _texto_plano(_hijo(meta_el, "TituloNorma"))
        materias = [v for e in meta_el.iter() if _tag(e) == "Materia" if (v := _texto_plano(e))]

    derogada = _es_si(attrs.get("derogado", ""), "derogado")
    m = _meta_base(cfg, id_norma, tipo, numero, titulo)
    vigente, anticipada = _politica_vigencia(cfg, "", "", not derogada, hoy)
    m.update(organismos=organismos, materias=materias, derogado=derogada,
             fecha_version=attrs.get("fechaVersion", ""),
             fecha_publicacion=ident.attrib.get("fechaPublicacion", "") if ident is not None else "",
             vigencia_desde="", vigencia_hasta="", vigente=vigente,
             vigencia_anticipada=anticipada)
    arm = _Armador(cfg, m)

    def caminar(contenedor, ruta: list[str], derogado_padre: bool):
        for ef in contenedor:
            if _tag(ef) != "EstructuraFuncional":
                continue
            tipo_parte = ef.attrib.get("tipoParte", "")
            derogado = derogado_padre or _es_si(ef.attrib.get("derogado", ""), "derogado")
            transitorio = _es_si(ef.attrib.get("transitorio", ""), "transitorio")
            md = _hijo(ef, "Metadatos")
            nombre_parte = _texto_plano(_hijo(md, "NombreParte")) if md is not None else ""
            titulo_parte = _texto_plano(_hijo(md, "TituloParte")) if md is not None else ""
            texto = _texto_incisos(_hijo(ef, "Texto"))
            sub = _hijo(ef, "EstructurasFuncionales")
            es_articulo = _slug(tipo_parte).startswith("articulo")
            if es_articulo and sub is not None and not _ENCABEZADO_ART.match(texto):
                # Encabezado marcado como artículo (p. ej. Código del Trabajo:
                # "ARTICULOS TRANSITORIOS" con tipoParte=Artículo y hijos).
                es_articulo = False

            if es_articulo:
                num = nombre_parte or str(len(arm.ids) + 1)
                etiqueta = f"Artículo {num}" + (" transitorio" if transitorio else "")
            elif _slug(tipo_parte) == "doble-articulado":
                etiqueta = ""  # contenedor técnico: no aporta a la jerarquía
            else:
                etiqueta = titulo_parte or (texto.split("\n")[0][:120] if texto else "") \
                    or nombre_parte or tipo_parte
            nueva_ruta = ruta + ([etiqueta] if etiqueta else [])

            if es_articulo and texto:
                arm.articulo(num=num, texto=texto, ruta=ruta, transitorio=transitorio,
                             derogado=derogado, fecha_version=ef.attrib.get("fechaVersion", ""),
                             id_parte=ef.attrib.get("idParte", ""), contiene_ley=sub is not None)

            # Siempre descender: un artículo puede contener un "Doble Articulado"
            # (p. ej. Ley 20.393: el Artículo Primero trae la ley completa).
            if sub is not None:
                caminar(sub, nueva_ruta, derogado)

    raiz = _hijo(norma_el, "EstructurasFuncionales")
    if raiz is not None:
        caminar(raiz, [], False)
    return _resultado(cfg, m, xml_bytes, arm)


# ----------------------------------------------------------------- fuente JSON
_NOMBRE_ART = re.compile(r"^\s*art[íi]culo\s+(.*?)\s*$", re.IGNORECASE)
_TRANSITORIO = re.compile(r"\s*transitori[oa]s?\s*$", re.IGNORECASE)
TIPO_ARTICULO_JSON = 6  # "t" de los nodos artículo en `estructura`


def parsear_json(datos: bytes, cfg: dict, hoy: date | None = None) -> tuple[dict, list[dict]]:
    d = json.loads(datos)
    md = d.get("metadatos") or {}
    id_norma = int(md.get("id_norma") or cfg.get("idNorma", 0))
    if cfg.get("idNorma") and id_norma != int(cfg["idNorma"]):
        raise ValueError(f"la BCN devolvió idNorma {id_norma}, se pidió {cfg['idNorma']}")
    tn = (md.get("tipos_numeros") or [{}])[0]
    m = _meta_base(cfg, id_norma, tn.get("descripcion", ""), str(tn.get("numero", "")),
                   md.get("titulo_norma", ""))

    # Vigencia de la versión entregada: la de `version`, o la "Última Versión".
    vigencias = md.get("vigencias") or []
    pedida = cfg.get("version")
    v = next((x for x in vigencias if x.get("desde") == pedida), None) if pedida else \
        next((x for x in vigencias if x.get("tipo_version") == "2"), None)
    if pedida and v is None:
        raise ValueError(f"la BCN no lista una versión que comience el {pedida} "
                         f"(versiones: {[x.get('desde') for x in vigencias][:8]})")
    desde, hasta = (v or {}).get("desde", ""), (v or {}).get("hasta", "")
    derogada = bool(md.get("derogado"))
    vigente, anticipada = _politica_vigencia(cfg, desde, hasta, not derogada, hoy)
    m.update(organismos=md.get("organismos", []), materias=md.get("materias", []),
             derogado=derogada, fecha_version=desde, fecha_publicacion=md.get("fecha_publicacion", ""),
             vigencia_desde=desde, vigencia_hasta=hasta, vigente=vigente,
             vigencia_anticipada=anticipada, tipo_version=(v or {}).get("tipo_version_s", ""))
    arm = _Armador(cfg, m)

    nombres: dict = {}

    def indexar(xs):
        for x in xs:
            nombres[x.get("i")] = (x.get("n", "").strip(), x.get("t"))
            indexar(x.get("h", []))
    indexar(d.get("estructura", []))

    solo_mod = cfg.get("solo_modificados_por")
    marca_mod = f"idNorma={solo_mod}&" if solo_mod else None

    def modificadores(t: str) -> list[str]:
        return sorted(set(re.findall(r"navegar\?idNorma=(\d+)&", t)))

    def caminar(nodos, ruta: list[str], en_transitorios: bool):
        for x in nodos:
            nombre, tipo = nombres.get(x.get("i"), ("", None))
            t_html = x.get("t", "")
            hijos = x.get("h", [])
            if tipo == TIPO_ARTICULO_JSON or _NOMBRE_ART.match(nombre):
                num = _NOMBRE_ART.match(nombre).group(1) if _NOMBRE_ART.match(nombre) else nombre
                transitorio = en_transitorios or bool(_TRANSITORIO.search(num))
                num = _TRANSITORIO.sub("", num).strip()
                texto = _texto_html(t_html)
                if texto and (marca_mod is None or marca_mod in t_html):
                    arm.articulo(num=num, texto=texto, ruta=ruta, transitorio=transitorio,
                                 derogado=False, fecha_version="", id_parte=x.get("i", ""),
                                 contiene_ley=bool(hijos), modificado_por=modificadores(t_html))
                if hijos:
                    caminar(hijos, ruta + [f"Artículo {num}"], transitorio)
                continue
            etiqueta = " ".join(nombre.split())
            if etiqueta.lower() in ("encabezado", "promulgación", "promulgacion") or \
                    etiqueta.lower().startswith("anexo"):
                continue
            caminar(hijos, ruta + ([etiqueta] if etiqueta else []),
                    en_transitorios or "transitori" in etiqueta.lower())

    caminar(d.get("html", []), [], False)
    return _resultado(cfg, m, datos, arm)


def parsear(crudo: bytes, cfg: dict, hoy: date | None = None) -> tuple[dict, list[dict]]:
    if fuente_de(cfg) == "json":
        return parsear_json(crudo, cfg, hoy)
    return parsear_xml(crudo, cfg, hoy)


# ---------------------------------------------------------------- persistencia
def _firma(f: dict) -> str:
    """Lo que, si cambia, obliga a re-embebir o actualizar el payload en Qdrant."""
    return _sha(json.dumps([f["texto_embedding"], f["vigente"], f["vigencia_anticipada"],
                            f["categorias"], f["tipo_contenido"]], ensure_ascii=False))


def guardar_local(doc_norma: dict, fragmentos: list[dict]) -> Path:
    SALIDA.mkdir(exist_ok=True)
    out = SALIDA / f"{_slug(doc_norma['clave'])}.json"
    out.write_text(json.dumps({"norma": doc_norma, "fragmentos": fragmentos},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def asegurar_indices(db):
    db.fragmentos.create_index("estado_embedding")
    db.fragmentos.create_index("clave_corpus")
    db.fragmentos.create_index("id_norma")
    db.fragmentos.create_index([("vigente", 1), ("tipo_contenido", 1)])
    db.fragmentos_historial.create_index("fragmento_id")
    db.normas_historial.create_index("clave")


def upsert_mongo(db, doc_norma: dict, fragmentos: list[dict], forzar: bool = False) -> dict:
    """Devuelve conteos {nuevos, cambiados, retirados}. Nunca borra documentos.

    Aunque la fuente no cambie, se re-evalúa la vigencia: así una vigencia
    anticipada o diferida se actualiza sola el día que corresponde (cron diario)."""
    from pymongo import ReplaceOne, UpdateOne

    res = {"nuevos": 0, "cambiados": 0, "retirados": 0, "sin_cambios": False}
    previa = db.normas.find_one({"_id": doc_norma["_id"]})
    misma_fuente = bool(previa) and previa.get("hash_fuente") == doc_norma["hash_fuente"]
    misma_vigencia = bool(previa) and \
        (previa.get("vigente"), previa.get("vigencia_anticipada")) == \
        (doc_norma["vigente"], doc_norma["vigencia_anticipada"])
    if misma_fuente and misma_vigencia and not forzar:
        res["sin_cambios"] = True
        return res
    if previa and not misma_fuente:
        previa["archivada_en"] = _ahora()
        previa["_id"] = f"{previa['clave']}@{previa.get('fecha_version') or 'na'}@{previa['hash_fuente'][:8]}"
        db.normas_historial.replace_one({"_id": previa["_id"]}, previa, upsert=True)
    db.normas.replace_one({"_id": doc_norma["_id"]}, doc_norma, upsert=True)

    existentes = {d["_id"]: d for d in db.fragmentos.find({"clave_corpus": doc_norma["clave"]})}
    ops, historial = [], []
    nuevos_ids = set()
    for f in fragmentos:
        nuevos_ids.add(f["_id"])
        f["firma"] = _firma(f)
        actual = existentes.get(f["_id"])
        if actual is None:
            res["nuevos"] += 1
        elif actual.get("firma") == f["firma"]:
            continue  # sin cambios: conserva su embedding
        else:
            res["cambiados"] += 1
            historial.append(actual)
            if actual.get("estado_embedding") == "ok" and actual.get("hash_texto") == f["hash_texto"] \
                    and f["estado_embedding"] == "pendiente":
                f["motivo_pendiente"] = "metadatos"  # solo cambió vigencia/categorías
        ops.append(ReplaceOne({"_id": f["_id"]}, f, upsert=True))

    for fid, actual in existentes.items():
        if fid in nuevos_ids or (actual.get("retirado_en") and not actual.get("vigente")):
            continue
        # Artículo que ya no aparece en la versión vigente (renumeración, error de
        # parseo previo...): se conserva, se marca no vigente y se re-sincroniza.
        historial.append(dict(actual))
        ops.append(UpdateOne({"_id": fid}, {"$set": {
            "vigente": False, "retirado_en": _ahora(),
            "estado_embedding": "pendiente" if actual.get("estado_embedding") == "ok"
            else actual.get("estado_embedding", "no_aplica")}}))
        res["retirados"] += 1

    if historial:
        for h in historial:
            h["fragmento_id"] = h["_id"]
            h["_id"] = f"{h['_id']}@{h.get('firma', '')[:12]}@{h.get('actualizado_en', '')}"
            h["archivado_en"] = _ahora()
        db.fragmentos_historial.bulk_write(
            [ReplaceOne({"_id": h["_id"]}, h, upsert=True) for h in historial], ordered=False)
    if ops:
        db.fragmentos.bulk_write(ops, ordered=False)
    return res


# ------------------------------------------------------------------------- CLI
def _cfg_desde_ref(ref: str) -> dict:
    """'idLey=21643', 'idNorma=1984', 'idNorma=141599@2026-12-01' (versión, vía json)."""
    version = ""
    if "@" in ref:
        ref, version = ref.split("@", 1)
    if "=" in ref:
        k, v = ref.split("=", 1)
        if k not in ("idLey", "idNorma"):
            raise SystemExit(f"referencia inválida: {ref} (usar idLey=N o idNorma=N)")
        cfg = {k: int(v)}
    else:
        cfg = {"idNorma": int(ref)}
    if version:
        cfg.update(fuente="json", version=version)
    return cfg


def _coincide(n: dict, filtros: list[str]) -> bool:
    for f in filtros:
        f_l = f.lower()
        if f_l in (str(n.get("idNorma", "")), str(n.get("idLey", "")), clave_de(n).lower()) or \
                f_l in n.get("nombre", "").lower():
            return True
    return False


def verificar(refs: list[str]):
    """Muestra metadatos para confirmar un id antes de agregarlo a leyes.json."""
    for i, ref in enumerate(refs):
        if i:
            time.sleep(PAUSA_SEGUNDOS)
        cfg = _cfg_desde_ref(ref)
        try:
            doc, frags = parsear(descargar(cfg), cfg)
        except Exception as e:  # noqa: BLE001
            print(f"ERR {ref}: {e}")
            continue
        tipos = {}
        for f in frags:
            tipos[f["tipo_contenido"]] = tipos.get(f["tipo_contenido"], 0) + 1
        print(f"{ref}\n  idNorma={doc['id_norma']}  {doc['tipo']} {doc['numero']}"
              f"  versión={doc['fecha_version'] or '-'}  derogada={doc['derogado']}\n"
              f"  Título: {doc['titulo']}\n"
              f"  Artículos: {doc['total_articulos']}  fragmentos: {len(frags)} {tipos}\n"
              f"  URL: {doc['url_fuente']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extractor del corpus normativo BCN")
    ap.add_argument("--config", default=str(DIR / "leyes.json"))
    ap.add_argument("--normas", nargs="+", metavar="ID_O_NOMBRE",
                    help="procesar solo estas entradas (idNorma, idLey, clave o parte del nombre); "
                         "incluye las marcadas activa=false")
    ap.add_argument("--solo-prioridad", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="no escribe en Mongo")
    ap.add_argument("--forzar", action="store_true",
                    help="re-evaluar fragmentos aunque la fuente no haya cambiado")
    ap.add_argument("--desde-cache", nargs="?", const=str(FUENTES), metavar="DIR",
                    help="leer las fuentes crudas desde DIR (defecto salida/fuentes) en vez de descargar")
    ap.add_argument("--verificar", nargs="+", metavar="REF",
                    help="solo mostrar metadatos de idLey=N / idNorma=N[@AAAA-MM-DD] y salir")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    if args.verificar:
        verificar(args.verificar)
        return 0

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    normas = cfg["normas"]
    claves = [clave_de(n) for n in normas]
    repetidas = {c for c in claves if claves.count(c) > 1}
    if repetidas:
        log.error("claves repetidas en %s: %s (agregar 'clave' única)", args.config, repetidas)
        return 2
    if args.normas:
        normas = [n for n in normas if _coincide(n, args.normas)]
        if not normas:
            log.error("ninguna entrada de %s coincide con %s", args.config, args.normas)
            return 2
    else:
        normas = [n for n in normas if n.get("activa", True)]
    if args.solo_prioridad is not None:
        normas = [n for n in normas if n.get("prioridad", 9) <= args.solo_prioridad]
    if not normas:
        log.warning("no hay normas activas que procesar (revisar 'activa' en %s)", args.config)
        return 0

    db = None
    uri = os.environ.get("MONGODB_URI")
    if uri and not args.dry_run:
        from pymongo import MongoClient
        db = MongoClient(uri).get_default_database()
        asegurar_indices(db)
    elif not args.dry_run:
        log.warning("MONGODB_URI no definida: solo se escriben JSON en %s", SALIDA)

    errores = 0
    descargas = 0
    for n in normas:
        try:
            if args.desde_cache:
                crudo = ruta_cache(n, Path(args.desde_cache)).read_bytes()
            else:
                if descargas:
                    time.sleep(PAUSA_SEGUNDOS)
                crudo = descargar(n)
                descargas += 1
                FUENTES.mkdir(parents=True, exist_ok=True)
                ruta_cache(n).write_bytes(crudo)
            doc, frags = parsear(crudo, n)
            if not frags:
                raise ValueError("0 fragmentos extraídos: revisar estructura de la fuente")
            guardar_local(doc, frags)
            tipos = {}
            for f in frags:
                tipos[f["tipo_contenido"]] = tipos.get(f["tipo_contenido"], 0) + 1
            msg = (f"OK  {n['nombre']} [{doc['clave']}, {doc['fuente']}, v{doc['fecha_version'] or '-'}]: "
                   f"{doc['total_articulos']} artículos, {len(frags)} fragmentos {tipos}, "
                   f"vigente={doc['vigente']}{' (anticipada)' if doc['vigencia_anticipada'] else ''}, "
                   f"{sum(not f['vigente'] for f in frags)} fragmentos no vigentes")
            if db is not None:
                r = upsert_mongo(db, doc, frags, forzar=args.forzar)
                msg += (" | sin cambios" if r["sin_cambios"] else
                        f" | {r['nuevos']} nuevos, {r['cambiados']} cambiados, "
                        f"{r['retirados']} retirados")
            log.info(msg)
        except Exception as e:  # noqa: BLE001
            errores += 1
            log.error("ERR %s: %s", n.get("nombre"), e)

    log.info("Fin: %s entradas, %s con error", len(normas), errores)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
