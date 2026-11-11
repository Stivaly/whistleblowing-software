"""Variantes del texto que se vectoriza por fragmento (`texto_embedding`), como funciones puras.

Entrada: un fragmento tal como lo guarda `job_embeddings/datos/fragmentos.json` ({"id", "texto_embedding",
"payload"}), o el payload solo. Salida: el texto a vectorizar. No toca Mongo ni Qdrant.

  base : el `texto_embedding` actual ("{referencia} — {nombre}. {jerarquía} > Artículo N. {texto}").
  A    : encabezado limpio `Ley N (nombre corto) · Art. N · <título> · materias`, y el texto sin el
         prefijo "Artículo N.- <título>." que el encabezado ya trae.
  AB   : A con un resumen de materia (lenguaje de denuncia) entre el encabezado y el texto.
"""
from __future__ import annotations

import re

NUMERO = r"[0-9A-Za-zÁÉÍÓÚáéíóú-]+(?:\s+(?:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|novies|decies))*"
PREFIJO = re.compile(
    rf'^"?\s*Art(?:[ií]culo|\.)\s*{NUMERO}\s*(?:[°º]|\.o\b)?\s*[.\-]*\s*', re.S)
TITULO = re.compile(r"^(?P<titulo>[^.\n:;]{3,120}?)\.(?=\s|$)")
MAX_PALABRAS_TITULO = 12
MAX_MATERIAS = 6
LARGO_RESUMEN = 420


def _payload(frag: dict) -> dict:
    return frag.get("payload", frag)


def separar_titulo(texto: str) -> tuple[str, str]:
    """-> (título, cuerpo). Quita el prefijo "Artículo N.-" y, si lo hay, el título corto que sigue.

    Sin título reconocible (artículos que parten directo con el contenido) el título es "". El título debe ser una
    frase corta sin dos puntos, que empiece con mayúscula y no pase de MAX_PALABRAS_TITULO palabras."""
    m = PREFIJO.match(texto)
    resto = texto[m.end():] if m else texto
    t = TITULO.match(resto)
    if t:
        titulo = t.group("titulo").strip()
        cuerpo = resto[t.end():].lstrip()
        if cuerpo and titulo[:1].isupper() and len(titulo.split()) <= MAX_PALABRAS_TITULO:
            return titulo, cuerpo
    return "", resto.strip()


def nombre_corto(norma: str) -> str:
    """Nombre de la norma sin el número, la nota de reforma ni el sufijo explicativo.

    'Ley 20.393 Responsabilidad penal de las personas jurídicas' -> 'Responsabilidad penal de las personas
    jurídicas'; 'Ley 21.643 (Ley Karin) acoso laboral...' -> 'Ley Karin: acoso laboral...';
    'Código del Trabajo: artículos incorporados ...' -> 'Código del Trabajo'."""
    n = re.sub(r"\s*\((?:reformada|modificada)[^)]*\)\s*$", "", norma.strip())
    n = re.sub(r"^Ley\s+[\d.]+\s*", "", n)
    n = re.sub(r"^\(([^)]+)\)\s*(.*)$", lambda m: f"{m.group(1)}: {m.group(2)}" if m.group(2) else m.group(1), n)
    n = n.split(":")[0] if n.startswith("Código") else n
    return n.strip()


def etiqueta_ley(p: dict) -> str:
    """'Ley 20.393'; si la norma no es una ley numerada (Código, DFL), su nombre corto."""
    m = re.match(r"^Ley\s+([\d.]+)", p["norma"])
    if m:
        return f"Ley {m.group(1)}"
    return nombre_corto(p["norma"])


def etiqueta_articulo(p: dict) -> str:
    art = str(p["articulo"]).strip()
    parte = p.get("parte") or ""
    return f"Art. {art}" + (f" (parte {parte})" if parte else "")


def materias_utiles(materias: list[str], maximo: int = MAX_MATERIAS) -> list[str]:
    """Materias BCN sin la etiqueta 'Ley no. N' (ya va en el encabezado), sin repetidas."""
    vistas, out = set(), []
    for m in materias or []:
        m = m.strip()
        if not m or re.match(r"^Ley\s+no\.", m, re.I) or m.lower() in vistas:
            continue
        vistas.add(m.lower())
        out.append(m)
    return out[:maximo]


def encabezado_a(frag: dict) -> str:
    p = _payload(frag)
    titulo, _ = separar_titulo(p["texto"])
    ley = etiqueta_ley(p)
    corto = nombre_corto(p["norma"])
    partes = [f"{ley} ({corto})" if corto and corto != ley else ley, etiqueta_articulo(p)]
    if titulo:
        partes.append(titulo)
    mats = materias_utiles(p.get("materias"))
    if mats:
        partes.append("Materias: " + ", ".join(mats))
    return " · ".join(partes)


def variante_a(frag: dict) -> str:
    """Encabezado limpio + texto sin el prefijo 'Artículo N.- título.'."""
    _, cuerpo = separar_titulo(_payload(frag)["texto"])
    return f"{encabezado_a(frag)}\n{cuerpo}"


def variante_ab(frag: dict, resumen: str) -> str:
    """Variante A con el resumen de materia entre el encabezado y el texto."""
    resumen = (resumen or "").strip()
    if not resumen:
        raise ValueError(f"sin resumen para {_payload(frag)['fragmento_id']}")
    _, cuerpo = separar_titulo(_payload(frag)["texto"])
    return f"{encabezado_a(frag)}\nResumen: {resumen}\n{cuerpo}"


def construir(frag: dict, variante: str, resumenes: dict[str, str] | None = None) -> str:
    """Texto a vectorizar de `frag` según la variante: 'base', 'A' o 'AB'."""
    if variante == "base":
        return frag["texto_embedding"]
    if variante == "A":
        return variante_a(frag)
    if variante == "AB":
        return variante_ab(frag, (resumenes or {}).get(_payload(frag)["fragmento_id"], ""))
    raise ValueError(f"variante desconocida: {variante}")


def prompt_resumen(frag: dict) -> str:
    """Instrucción para que un LLM resuma la materia del artículo en el lenguaje en que una persona la
    describiría al denunciar. No incluye consultas ni denuncias del dataset."""
    p = _payload(frag)
    return (
        "Eres un asistente jurídico chileno. Resume de qué trata el siguiente artículo en 2 o 3 oraciones "
        f"(unos {LARGO_RESUMEN} caracteres como máximo), con palabras sencillas y en el lenguaje con que una "
        "persona común describiría un hecho que podría denunciar o consultar (conductas, situaciones, "
        "derechos u obligaciones concretas), sin citar números de artículos y sin inventar nada que el texto "
        "no diga. Responde solo con el resumen, sin comillas ni viñetas.\n\n"
        f"Norma: {p['norma']}\n{etiqueta_articulo(p)}\n\nTexto:\n{p['texto'][:6000]}"
    )


def limpiar_resumen(texto: str, maximo: int = 600) -> str:
    """Una sola línea, sin comillas ni viñetas, recortada en una oración completa si se pasa de `maximo`."""
    t = re.sub(r"\s+", " ", texto or "").strip().strip('"«»').lstrip("-*• ").strip()
    if len(t) > maximo:
        corte = t[:maximo]
        punto = corte.rfind(". ")
        t = corte[:punto + 1] if punto > maximo // 2 else corte.rstrip()
    return t
