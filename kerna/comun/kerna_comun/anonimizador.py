"""Anonimizador por reglas (solo biblioteca estandar, sin modelos).

Sustituye identificadores por marcadores estables y numerados por valor distinto
(`[PERSONA_1]`, `[RUT_1]`, ...). Solo sustituye: nunca interpreta el texto, de modo que
instrucciones incrustadas en el no tienen efecto. Es determinista e idempotente.

Para ampliar las reglas: listas `EXCEPCIONES_*`, `TRATAMIENTOS` y `NOMBRES_CONOCIDOS`
(nombres propios), `COMUNAS` (direcciones) y las expresiones de cada tipo. Ver kerna/comun/README.md.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

TIPOS = ("PERSONA", "RUT", "CORREO", "TELEFONO", "DIRECCION", "PATENTE", "CUENTA", "URL")


@dataclass
class Resultado:
    texto: str
    conteos: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Listas ampliables (todas en minusculas y sin tildes)
# ---------------------------------------------------------------------------

# Palabras que nunca forman parte de un nombre de persona: leyes, instituciones, siglas,
# cargos y terminos de uso comun que suelen escribirse con mayuscula.
EXCEPCIONES_PALABRAS = set("""
ley leyes codigo articulo articulos art inciso decreto dfl dl ds reglamento norma estatuto constitucion
protocolo politica reglamento circular ordinario resolucion sentencia fallo
direccion inspeccion ministerio fiscalia contraloria superintendencia agencia servicio tribunal tribunales
juzgado corte camara senado gobierno municipalidad municipal subsecretaria intendencia gobernacion
poder judicial publico publica policia investigaciones carabineros defensoria consejo comision comite
gerencia subgerencia departamento area unidad jefatura division seccion sucursal oficina local
recursos humanos personas proteccion datos personales trabajo trabajos karin seguridad social salud
laboral laborales prevencion riesgos mercado financiero impuestos internos aduanas tesoreria
chile chilena chileno republica region metropolitana nacional nacionales estado fisco
spa ltda eirl limitada asesorias asesoria consultoria consultoras servicios transportes transporte constructoras distribuidora
banco empresa empresas sociedad compania corporacion fundacion universidad hospital clinica colegio
instituto liceo inversiones comercial constructora grupo sindicato federacion confederacion mutual
isapre fonasa afp cmf sii suseso dt cgr pdi mp afc ips seremi
lunes martes miercoles jueves viernes sabado domingo
enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre
gracias saludos estimado estimada estimados estimadas atentamente cordialmente buenos buenas dias tardes noches
usted ustedes yo
general directo directa titular
whatsapp facebook instagram google microsoft teams zoom tiktok linkedin twitter
""".split())

# Frases (varias palabras) que se tratan como excepcion completa.
EXCEPCIONES_FRASES = [
    "santiago centro", "puente alto", "las condes", "lo barnechea", "la reina", "la florida", "la cisterna",
    "la pintana", "la granja", "lo espejo", "el bosque", "san bernardo", "san miguel", "san joaquin",
    "san ramon", "pedro aguirre cerda", "estacion central", "quinta normal", "villa alemana",
    "vina del mar", "san antonio", "los angeles", "padre las casas", "puerto montt", "puerto varas",
    "punta arenas", "la serena", "alto hospicio", "san pedro de la paz", "lo prado", "cerro navia",
    "isla de maipo", "buin paine", "region de valparaiso", "region del biobio", "region de los lagos",
    "tierra del fuego", "arica y parinacota", "viña del mar",
]

# Tratamientos y cargos: la palabra que los sigue (con mayuscula) es un nombre propio.
TRATAMIENTOS = set("""
don dona senor senora senorita sr sra srta dr dra doctor doctora
jefe jefa gerente subgerente supervisor supervisora director directora subdirector subdirectora
companero companera colega encargado encargada coordinador coordinadora administrador administradora
abogado abogada ingeniero ingeniera profesor profesora ejecutivo ejecutiva vendedor vendedora
cajero cajera guardia chofer conductor contador contadora secretario secretaria analista asistente
trabajador trabajadora funcionario funcionaria empleado empleada vecino vecina denunciado denunciada
acusado acusada testigo esposo esposa marido pareja hermano hermana padre madre hijo hija tio tia
primo prima amigo amiga capataz mayordomo bodeguero operador operadora tecnico tecnica
""".split())

# Disparadores de contexto inmediatamente antes de un nombre.
_DISPARADORES = re.compile(
    r"(?i:me llamo|mi nombre es|se llama|llamad[oa]|de nombre|nombre(?: completo)?:|denuncio a|apellidos?:)[ \t]*$")

# Palabras que abren oracion con mayuscula y no son nombres (se recortan del inicio de un candidato).
INICIOS_DE_ORACION = set("""
ayer hoy manana luego despues antes entonces ademas tambien sin pero porque cuando mientras desde hasta
segun durante ahora siempre nunca incluso aunque sino como donde asi aqui alli ese esa esos esas este esta
estos estas el la los las un una unos unas mi mis su sus nuestro nuestra todo toda todos todas cada otro
otra otros otras alguien nadie nada algo ya aun solo solamente primero segundo tercero finalmente luego
posteriormente inmediatamente recientemente actualmente tambien por para con en al del se me te le les
no si que y e o u ni
""".split())

# Nombres de pila frecuentes en Chile (ayudan a decidir al inicio de una oracion).
NOMBRES_CONOCIDOS = set("""
maria jose juan luis carlos jorge pedro pablo miguel manuel francisco cristian cristobal daniel diego
felipe fernando gabriel gonzalo hector hernan ignacio javier joaquin julio marcelo marcos mario mauricio
nicolas oscar patricio rafael ricardo roberto rodrigo sebastian sergio victor claudio claudia camila
carolina catalina constanza daniela fernanda francisca gabriela javiera jessica karen laura macarena
marcela margarita natalia paola paula patricia pamela andrea ana angelica alejandra alicia barbara
beatriz carmen cecilia cristina elena eliana elizabeth erika gloria graciela ines isabel jimena karina
lorena lucia luz marta mercedes monica nancy nelly noelia olga pilar rosa rocio sandra silvia sofia
soledad tatiana teresa valentina valeria veronica viviana ximena yasna yolanda andres alberto alejandro
alfredo alonso antonio armando arturo benjamin bruno cesar eduardo emilio enrique ernesto esteban eugenio
exequiel fabian german guillermo gustavo hugo ivan jaime jeremias leonardo lucas mathias mauro maximiliano
nelson omar osvaldo raul renato rene ruben samuel santiago tomas vicente waldo wilson xavier
""".split())

COMUNAS = [
    "santiago", "providencia", "las condes", "vitacura", "lo barnechea", "ñuñoa", "la reina", "macul",
    "peñalolén", "la florida", "puente alto", "san bernardo", "maipú", "pudahuel", "cerrillos",
    "estación central", "quinta normal", "renca", "independencia", "recoleta", "conchalí", "huechuraba",
    "quilicura", "colina", "lampa", "la cisterna", "san miguel", "san joaquín", "pedro aguirre cerda",
    "lo espejo", "el bosque", "la pintana", "san ramón", "la granja", "lo prado", "cerro navia",
    "valparaíso", "viña del mar", "quilpué", "villa alemana", "concón", "quillota", "san antonio",
    "concepción", "talcahuano", "hualpén", "san pedro de la paz", "chiguayante", "coronel", "antofagasta",
    "calama", "iquique", "alto hospicio", "arica", "copiapó", "la serena", "coquimbo", "ovalle", "rancagua",
    "machalí", "talca", "curicó", "linares", "chillán", "los ángeles", "temuco", "padre las casas",
    "villarrica", "valdivia", "osorno", "puerto montt", "puerto varas", "castro", "coyhaique",
    "punta arenas", "padre hurtado", "peñaflor", "talagante", "melipilla", "buin", "paine", "calera de tango",
]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _sin_tildes(s: str) -> str:
    d = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def _dv_rut(cuerpo: str) -> str:
    suma, factor = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return "0" if resto == 11 else "k" if resto == 10 else str(resto)


def rut_valido(texto: str) -> bool:
    limpio = re.sub(r"[^0-9kK]", "", texto).lower()
    if not 8 <= len(limpio) <= 9 or not limpio[:-1].isdigit():
        return False
    return limpio[-1] == _dv_rut(limpio[:-1])


def _luhn(texto: str) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", texto)]
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, x in enumerate(reversed(d)):
        if i % 2:
            x *= 2
            if x > 9:
                x -= 9
        total += x
    return total % 10 == 0


class _Mapa:
    """Marca los caracteres ya asignados a un identificador (cada regla respeta lo anterior)."""

    def __init__(self, n: int):
        self.ocupado = bytearray(n)

    def libre(self, i: int, f: int) -> bool:
        return not any(self.ocupado[i:f])

    def tomar(self, i: int, f: int) -> None:
        self.ocupado[i:f] = b"\x01" * (f - i)


_MARCADOR = re.compile(r"\[(" + "|".join(TIPOS) + r")_(\d+)\]")

# ---------------------------------------------------------------------------
# Expresiones por tipo
# ---------------------------------------------------------------------------

_COMUNAS_RE = "|".join(re.escape(c) for c in sorted(COMUNAS, key=len, reverse=True))

_CORREO = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL_ESQUEMA = re.compile(r"(?i:\b(?:https?://|www\.))[^\s<>\"']*[^\s<>\"'.,;:!?)\]]")
_URL_DOMINIO = re.compile(
    r"(?<![\w@./-])(?:[A-Za-z0-9-]+\.)+(?:cl|com|net|org|io|info|edu|gob|gov)(?:\.[a-z]{2})?"
    r"(?:/[^\s<>\"']*[^\s<>\"'.,;:!?)\]])?(?![\w@-])")

_RUT_PUNTOS = re.compile(r"(?<![\w$.,-])\d{1,2}(?:\.\d{3}){2}[ ]?-[ ]?[\dkK](?!\w)")
_RUT_GUION = re.compile(r"(?<![\w$.,-])\d{7,8}[ ]?-[ ]?[\dkK](?!\w)")
_RUT_CONTEXTO = re.compile(
    r"(?i:\b(?:rut|run|r\.u\.t\.?|c[eé]dula|c\.i\.?|dni)\b)[ \t:.n°º#]*"
    r"(\d{1,2}(?:\.?\d{3}){2}(?:[ ]?-?[ ]?[\dkK])?)(?![\w])")

_CUENTA_FILL = (r"(?i:corriente|cte|vista|rut|ahorro|bancaria|bancario|de|del|numero|número|nro|n[°º]|no|"
                r"credito|crédito|debito|débito|banco|estado|santander|chile|bci|itau|itaú|scotiabank|"
                r"falabella|ripley|security|bice|consorcio|n\.?[°º])")
_CUENTA_CONTEXTO = re.compile(
    r"(?i:\b(?:cuenta|cta|tarjeta|iban)\b)(?:[ \t.:,#-]+" + _CUENTA_FILL + r"(?!\w)\.?)*[ \t.:,#°º-]*"
    r"(\d(?:[ .-]?\d){5,24})(?!\d)")
_TARJETA_GRUPOS = re.compile(r"(?<![\w$.,-])\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4}(?!\d)")
_TARJETA_LUHN = re.compile(r"(?<![\w$.,-])\d(?:[ -]?\d){12,18}(?!\d)")

_PREF = r"(?:(?:\+|\(\+?)56\)?[ .-]?)"
_TEL_CL = re.compile(
    r"(?<![\w$.,])(?:"
    + _PREF + r"?\(?9\)?[ .-]?\d{4}[ .-]?\d{4}"
    + r"|" + _PREF + r"?\(?2\)?[ .-]?\d{4}[ .-]?\d{4}"
    + r"|" + _PREF + r"?\(?(?:3[2-5]|4[1-5]|5[1-8]|6[1-5]|7[1-5])\)?[ .-]?\d{3}[ .-]?\d{4}"
    + r"|" + _PREF + r"\(?\d{1,2}\)?[ .-]?\d{3,4}[ .-]?\d{4}"
    + r")(?![\w]|[.,]\d)")
_TEL_INT = re.compile(r"(?<![\w])\+(?!56)\d{1,3}(?:[ .-]?\(?\d{1,4}\)?){2,5}(?!\d)")

_PATENTE_CONTEXTO = re.compile(
    r"(?i:\b(?:patente|placa)\b)(?:[ \t]+(?i:n[°º]|numero|número))?[ \t:]*"
    r"([A-Za-z]{2}[ -]?[A-Za-z]{2}[ -]?\d{2}|[A-Za-z]{4}[ -]?\d{2}|[A-Za-z]{2}[ -]?\d{4})(?![\w])")
_PATENTE = re.compile(
    r"(?<![\w-])(?:[A-Z]{2}[ -]?[A-Z]{2}[ -]?\d{2}|[BCDFGHJKLPRSTVWXYZ]{4}[ -]?\d{2})(?![\w-])")

_TOK = r"[A-ZÁÉÍÓÚÑ][\w'’-]*"
_NOMBRE_CALLE = (r"(?:" + _TOK + r"|\d{1,2}(?!\d))(?:[ \t]+(?:(?:de|del|la|las|los|el|y)[ \t]+)*(?:"
                 + _TOK + r"|\d{1,2}(?!\d))){0,4}")
_NUMERO = r"[ \t,]*(?i:(?:n[°º]|n\.°|nro\.?|numero|número|#)[ \t]*)?\d{1,5}(?!\d)"
_EXTRA = (r"(?:[ \t]*,?[ \t]*(?i:depto|dpto|departamento|oficina|of|casa|block|torre|piso)\.?[ \t]*"
          r"(?:(?i:n[°º]\.?)[ \t]*|#)?(?:\d{1,4}[A-Za-z]?|(?-i:[A-Z]))(?!\w)){0,3}")
_COMUNA_OPC = r"(?:[ \t]*,?[ \t]*(?i:comuna[ \t]+de[ \t]+)?(?i:" + _COMUNAS_RE + r")\b)?"
_COLA = _NUMERO + _EXTRA + _COMUNA_OPC
_DIRECCION = re.compile(
    r"(?<!\w)(?i:calle|avenida|avda?\.?|av\.?|pasaje|psje\.?|pje\.?|camino|poblaci[oó]n|pobl\.?|villa|condominio|parcela)[ \t]+" + _NOMBRE_CALLE + _COLA)
_DIRECCION_CTX = re.compile(
    r"(?i:domicilio|direcci[oó]n)[ \t]*(?i:es|:|en)[ \t]+(?P<d>" + _NOMBRE_CALLE + _COLA + r")")

_PALABRA = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
_SEP_ESPACIOS = re.compile(r"^[ \t\u00a0]+$")
_SEP_TITULO = re.compile(r"^\.?[ \t\u00a0]+$")
_CONECTORES_VALIDOS = {("de",), ("del",), ("de", "la"), ("de", "los"), ("de", "las")}


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------

def _clave_digitos(s: str) -> str:
    return re.sub(r"\D", "", s)


def _clave_rut(s: str) -> str:
    return re.sub(r"[^0-9kK]", "", s).lower()


def _clave_tel(s: str) -> str:
    d = _clave_digitos(s)
    if s.lstrip("( ").startswith("+56") or (len(d) > 9 and d.startswith("56")):
        d = d[2:] if d.startswith("56") else d
    return d


def _clave_texto(s: str) -> str:
    return re.sub(r"\s+", " ", _sin_tildes(s)).strip()


def _clave_patente(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", s).upper()


def _clave_url(s: str) -> str:
    return s.lower().rstrip("/")


def _tel_int_valido(s: str) -> bool:
    return 8 <= len(_clave_digitos(s)) <= 15


def _rut_guion_valido(s: str) -> bool:
    return rut_valido(s)


# (tipo, regex, grupo, validador, clave)
_REGLAS = [
    ("CORREO", _CORREO, 0, None, str.lower),
    ("URL", _URL_ESQUEMA, 0, None, _clave_url),
    ("URL", _URL_DOMINIO, 0, None, _clave_url),
    ("RUT", _RUT_PUNTOS, 0, None, _clave_rut),
    ("RUT", _RUT_GUION, 0, _rut_guion_valido, _clave_rut),
    ("RUT", _RUT_CONTEXTO, 1, None, _clave_rut),
    ("CUENTA", _TARJETA_GRUPOS, 0, None, _clave_digitos),
    ("CUENTA", _TARJETA_LUHN, 0, _luhn, _clave_digitos),
    ("CUENTA", _CUENTA_CONTEXTO, 1, None, _clave_digitos),
    ("TELEFONO", _TEL_CL, 0, None, _clave_tel),
    ("TELEFONO", _TEL_INT, 0, _tel_int_valido, _clave_digitos),
    ("PATENTE", _PATENTE_CONTEXTO, 1, None, _clave_patente),
    ("PATENTE", _PATENTE, 0, None, _clave_patente),
    ("DIRECCION", _DIRECCION, 0, None, _clave_texto),
    ("DIRECCION", _DIRECCION_CTX, "d", None, _clave_texto),
]


def _aplicar_reglas(texto: str, mapa: _Mapa, spans: list) -> None:
    for tipo, regex, grupo, validar, clave in _REGLAS:
        for m in regex.finditer(texto):
            i, f = m.span(grupo)
            if i < 0 or not mapa.libre(i, f):
                continue
            valor = texto[i:f]
            if validar and not validar(valor):
                continue
            mapa.tomar(i, f)
            spans.append((i, f, tipo, clave(valor)))


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

_FRASES_POR_INICIO: dict = {}
for _f in EXCEPCIONES_FRASES:
    _p = tuple(_sin_tildes(_f).split())
    _FRASES_POR_INICIO.setdefault(_p[0], []).append(_p)


def _inicio_de_oracion(texto: str, ini: int) -> bool:
    previo = texto[:ini].rstrip(" \t\u00a0")
    return not previo or previo[-1] in '.!?\n:¿¡"“«(•*-)'


def _personas(texto: str, mapa: _Mapa, spans: list) -> None:
    pal = [(m.start(), m.end(), m.group(0)) for m in _PALABRA.finditer(texto)]
    n = len(pal)
    norm = [_sin_tildes(p[2]) for p in pal]
    excl = [mapa.ocupado_ini(p[0], p[1]) or norm[i] in EXCEPCIONES_PALABRAS for i, p in enumerate(pal)]
    for i in range(n):
        for frase in _FRASES_POR_INICIO.get(norm[i], ()):
            if tuple(norm[i:i + len(frase)]) == frase:
                for k in range(i, i + len(frase)):
                    excl[k] = True

    def cap(i: int) -> bool:
        w = pal[i][2]
        return w[0].isupper() and len(w) >= 2 and (not w.isupper() or len(w) >= 3)

    es_nombre = [not excl[i] and cap(i) and norm[i] not in TRATAMIENTOS_CAP for i in range(n)]
    es_conector = [not excl[i] and pal[i][2].islower() and norm[i] in ("de", "del", "la", "las", "los")
                   for i in range(n)]

    def contiguo(a: int, b: int) -> bool:
        return bool(_SEP_ESPACIOS.match(texto[pal[a][1]:pal[b][0]]))

    candidatos = []  # (ini, fin, tokens normalizados)
    secuencias = set()
    usado = set()
    i = 0
    while i < n:
        if not es_nombre[i]:
            i += 1
            continue
        run = [i]
        j = i
        while True:
            k = j + 1
            if k < n and contiguo(j, k) and es_nombre[k]:
                run.append(k)
                j = k
                continue
            c = k
            while c < n and c - k < 2 and contiguo(c - 1, c) and es_conector[c]:
                c += 1
            conect = tuple(norm[x] for x in range(k, c))
            if c > k and c < n and conect in _CONECTORES_VALIDOS and contiguo(c - 1, c) and es_nombre[c]:
                run.extend(range(k, c + 1))
                j = c
                continue
            break
        i = run[-1] + 1

        primero = run[0]
        contexto = False
        if primero > 0 and norm[primero - 1] in TRATAMIENTOS and _SEP_TITULO.match(
                texto[pal[primero - 1][1]:pal[primero][0]]):
            contexto = True
        elif _DISPARADORES.search(texto[max(0, pal[primero][0] - 40):pal[primero][0]]):
            contexto = True

        if not contexto and _inicio_de_oracion(texto, pal[primero][0]):
            while run:
                t = norm[run[0]]
                nombres_run = [x for x in run if not es_conector[x]]
                if t in NOMBRES_CONOCIDOS:
                    break
                if t in INICIOS_DE_ORACION or (len(nombres_run) >= 2 and norm[nombres_run[1]] in NOMBRES_CONOCIDOS):
                    run = run[1:]
                    while run and es_conector[run[0]]:
                        run = run[1:]
                    continue
                break
        nombres = [x for x in run if not es_conector[x]]
        if not nombres or len(nombres) > 5:
            continue
        if not contexto:
            if len(nombres) < 2:
                continue
            if any(pal[x][2].isupper() for x in nombres) and not any(norm[x] in NOMBRES_CONOCIDOS for x in nombres):
                continue
        candidatos.append((pal[run[0]][0], pal[run[-1]][1], frozenset(norm[x] for x in nombres)))
        usado.update(run)
        if len(nombres) >= 2:
            secuencias.add(tuple(norm[x] for x in nombres))

    # Mismo nombre completo escrito sin mayusculas iniciales ("pedro soto").
    extra = []
    for seq in sorted(secuencias):
        for x in range(n):
            if x in usado or excl[x] or norm[x] != seq[0]:
                continue
            idx, y, ok = [x], x, True
            for t in seq[1:]:
                y += 1
                while y < n and es_conector[y]:
                    y += 1
                if y >= n or excl[y] or norm[y] != t or not _SEP_ESPACIOS.match(texto[pal[y - 1][1]:pal[y][0]]):
                    ok = False
                    break
                idx.append(y)
            if ok and not any(z in usado for z in range(x, idx[-1] + 1)):
                extra.append((pal[x][0], pal[idx[-1]][1], frozenset(seq)))
                usado.update(range(x, idx[-1] + 1))
    candidatos += extra
    claves = {c[2] for c in candidatos}

    # Fusion de nombres incompletos con el unico nombre mas completo que los contiene.
    claves = {c[2] for c in candidatos}
    canon = {}
    for k in claves:
        actual = k
        for _ in range(4):
            sup = [s for s in claves if actual < s]
            if len(sup) != 1:
                break
            actual = sup[0]
        canon[k] = actual

    # Apariciones sueltas de un nombre o apellido ya visto (si identifica a una sola persona).
    alias: dict = {}
    for k in set(canon.values()):
        for t in k:
            if len(t) >= 3:
                alias.setdefault(t, set()).add(k)
    resultado = [(i, f, canon[k]) for i, f, k in candidatos]
    ocupados = [(i, f) for i, f, _ in candidatos]
    for x in range(n):
        if x in usado or excl[x] or not cap(x) or norm[x] in TRATAMIENTOS_CAP:
            continue
        dueños = alias.get(norm[x])
        if dueños and len(dueños) == 1 and not any(i <= pal[x][0] < f for i, f in ocupados):
            resultado.append((pal[x][0], pal[x][1], next(iter(dueños))))

    for i, f, k in resultado:
        mapa.tomar(i, f)
        spans.append((i, f, "PERSONA", "|".join(sorted(k))))


TRATAMIENTOS_CAP = TRATAMIENTOS  # los tratamientos escritos con mayuscula tampoco son nombres


def _ocupado_ini(self, i, f):
    return any(self.ocupado[i:f])


_Mapa.ocupado_ini = _ocupado_ini


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def anonimizar(texto: str) -> Resultado:
    """Sustituye los identificadores por marcadores. No interpreta el texto."""
    if not texto:
        return Resultado(texto=texto or "", conteos={})
    mapa = _Mapa(len(texto))
    base = {t: 0 for t in TIPOS}
    for m in _MARCADOR.finditer(texto):  # los marcadores existentes no se tocan ni se renumeran
        mapa.tomar(*m.span())
        base[m.group(1)] = max(base[m.group(1)], int(m.group(2)))

    spans: list = []
    _aplicar_reglas(texto, mapa, spans)
    _personas(texto, mapa, spans)
    spans.sort()

    numeros: dict = {}
    contadores = dict(base)
    partes, pos = [], 0
    for i, f, tipo, clave in spans:
        k = (tipo, clave)
        if k not in numeros:
            contadores[tipo] += 1
            numeros[k] = contadores[tipo]
        partes.append(texto[pos:i])
        partes.append(f"[{tipo}_{numeros[k]}]")
        pos = f
    partes.append(texto[pos:])
    conteos: dict = {}
    for tipo, _ in numeros:
        conteos[tipo] = conteos.get(tipo, 0) + 1
    return Resultado(texto="".join(partes), conteos=conteos)


def _compactar(s: str) -> str:
    s = _sin_tildes(s)
    s = re.sub(r"(?<=\d)[ .\-](?=\d)", "", s)  # 12.345.678-5 -> 123456785 ; 9 1234 5678 -> 912345678
    s = re.sub(r"(?<=\d)[ .\-](?=[k])", "", s)
    return re.sub(r"\s+", " ", s.replace(".", "")).strip()


def contiene_identificadores(texto: str, identificadores: list[str]) -> list[str]:
    """Devuelve los identificadores que siguen apareciendo en el texto.

    Comparacion insensible a mayusculas, tildes, puntos y espacios entre digitos.
    """
    plano = _compactar(texto)
    sobrevive = []
    for ident in identificadores:
        variantes = {_compactar(ident)}
        dig = _clave_digitos(ident)
        if ident.strip().startswith("+56") and len(dig) > 9:
            variantes.add(dig[2:])
        for v in list(variantes):
            variantes.add(re.sub(r"[ \-]", "", v)) if re.fullmatch(r"[\d +\-()]+k?", v) else None
        if any(v and re.search(r"(?<![\w])" + re.escape(v) + r"(?![\w])", plano) for v in variantes):
            sobrevive.append(ident)
    return sobrevive
