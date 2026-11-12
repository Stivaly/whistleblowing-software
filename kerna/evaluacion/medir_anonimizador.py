#!/usr/bin/python3
"""Mide el anonimizador por reglas (kerna_comun.anonimizador) sobre texto_original de los 113 casos.

Sin modelos ni red. Referencia: columna pii_en_texto (tipos presentes por caso) y detectores independientes
de verificación sobre el texto residual (conteo de apariciones que se le escapan). No imprime PII.
Uso (desde kerna/): /usr/bin/python3 evaluacion/medir_anonimizador.py [--json salida.json]
"""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "comun"))
from kerna_comun.anonimizador import anonimizar, rut_valido  # noqa: E402

DATASET = RAIZ / "evaluacion" / "datos" / "denuncias_publicas.json"

# etiqueta de pii_en_texto -> tipo del anonimizador (None = el anonimizador no tiene ese tipo)
def tipo_etiqueta(e):
    e = e.lower()
    if "correo" in e: return "CORREO"
    if e.startswith("rut"): return "RUT"
    if "teléfono" in e or "telefono" in e: return "TELEFONO"
    if "persona" in e or "iniciales" in e: return "PERSONA"
    if "dirección" in e or "direccion" in e: return "DIRECCION"
    if "ubicación" in e: return "UBICACION"
    if "empresa" in e or "institucion" in e: return "EMPRESA/INSTITUCION"
    if "causa" in e: return "N_CAUSA"
    if "cargo" in e: return "CARGO"
    if "edad" in e: return "EDAD"
    if "salud" in e: return "SALUD"
    if "nacionalidad" in e: return "NACIONALIDAD"
    if "género" in e: return "GENERO"
    if "financier" in e: return "FINANCIERO"
    if "ninguno" in e: return None
    return "OTRO"

# detectores independientes para contar apariciones reales (solo estructurados)
RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RE_RUT = re.compile(r"\b\d{1,2}(?:\.\d{3}){2}-[\dkK]\b|\b\d{7,8}-[\dkK]\b")
RE_TEL = re.compile(r"(?<!\d)(?:\+?56[ -]?)?9[ -]?\d{4}[ -]?\d{4}(?!\d)")
RE_EDAD = re.compile(r"\b\d{1,2} años\b|\btengo \d{2}\b|\b\d{2} años de edad\b")
RE_CAUSA = re.compile(r"\b(?:RIT|RUC|ROL)\b[: ]*[A-Z]?-?\d+[-\d]*", re.I)
RE_MARC = re.compile(r"\[(?:PERSONA|RUT|CORREO|TELEFONO|DIRECCION|PATENTE|CUENTA|URL)_\d+\]")


def main():
    casos = json.loads(DATASET.read_text(encoding="utf-8"))["casos"]
    ref = Counter(); det_caso = Counter()          # casos con la etiqueta / casos con >=1 detección del tipo
    marc_total = Counter(); casos_det = Counter()
    ocurr = defaultdict(lambda: [0, 0])            # tipo -> [apariciones en original, ocultas]
    residuo = Counter(); residuo_casos = Counter()
    exacto = defaultdict(lambda: [0, 0])           # por tipo mapeado: [casos con etiqueta, casos con detección]
    n_aptos = Counter()
    for c in casos:
        t = c["texto_original"]
        r = anonimizar(t)
        for k, v in r.conteos.items():
            marc_total[k] += v; casos_det[k] += 1
        etiquetas = {tipo_etiqueta(e.strip()) for e in c["pii_en_texto"].split(";")} - {None}
        for e in etiquetas:
            ref[e] += 1
            if e in r.conteos or (e == "UBICACION" and "DIRECCION" in r.conteos):
                det_caso[e] += 1
        # apariciones estructuradas
        for nombre, rx, tipo in (("CORREO", RE_CORREO, "CORREO"), ("RUT", RE_RUT, "RUT"), ("TELEFONO", RE_TEL, "TELEFONO")):
            todas = rx.findall(t)
            if nombre == "RUT":
                todas = [x for x in todas if rut_valido(x)]
            ocurr[nombre][0] += len(todas)
            quedan = rx.findall(r.texto)
            if nombre == "RUT":
                quedan = [x for x in quedan if rut_valido(x)]
            ocurr[nombre][1] += len(todas) - len(quedan)
            if quedan: residuo[nombre] += len(quedan); residuo_casos[nombre] += 1
        for nombre, rx in (("EDAD", RE_EDAD), ("N_CAUSA", RE_CAUSA)):
            a = len(rx.findall(t)); b = len(rx.findall(r.texto))
            ocurr[nombre][0] += a; ocurr[nombre][1] += a - b
            if b: residuo[nombre] += b; residuo_casos[nombre] += 1
        if c["apto_triggers_anonimizador"] == "sí": n_aptos["si"] += 1
    # sobre-enmascaramiento: marcadores PERSONA en casos sin etiqueta de persona; telefonos que son N° de causa
    sin_per = [c for c in casos if tipo_etiqueta("persona") not in {tipo_etiqueta(e.strip()) for e in c["pii_en_texto"].split(";")}]
    per_sin = sum(anonimizar(c["texto_original"]).conteos.get("PERSONA", 0) for c in sin_per)
    tel_causa = sum(len(re.findall(r"(?:N°|N\u00ba|nro\.?|rol|RIT)\s*\[TELEFONO_\d+\]", anonimizar(c["texto_original"]).texto, re.I)) for c in casos)
    from kerna_comun.anonimizador import NOMBRES_CONOCIDOS, _sin_tildes
    pila = 0; pila_casos = 0
    for c in casos:
        res = anonimizar(c["texto_original"]).texto
        k = sum(1 for m in re.finditer(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\b(?=\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)", res)
                if _sin_tildes(m.group(1)) in NOMBRES_CONOCIDOS and m.start() > 0 and res[m.start()-1] not in ".\n")
        pila += k; pila_casos += bool(k)
    salida = {
        "persona_en_casos_sin_etiqueta": {"casos": len(sin_per), "marcadores": per_sin},
        "telefono_que_es_numero_de_causa": tel_causa,
        "residuo_nombre_pila_conocido_seguido_de_mayuscula": {"apariciones": pila, "casos": pila_casos},
        "n_casos": len(casos), "casos_con_etiqueta": dict(ref), "casos_con_deteccion_del_tipo": dict(det_caso),
        "marcadores_emitidos": dict(marc_total), "casos_con_marcador": dict(casos_det),
        "apariciones_independientes": {k: {"total": v[0], "ocultas": v[1]} for k, v in ocurr.items()},
        "residuo_apariciones": dict(residuo), "residuo_casos": dict(residuo_casos),
    }
    # estabilidad: idempotencia
    salida["idempotente"] = all(anonimizar(anonimizar(c["texto_original"]).texto).texto == anonimizar(c["texto_original"]).texto for c in casos)
    print(json.dumps(salida, ensure_ascii=False, indent=1))
    if "--json" in sys.argv:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import tabla_evaluaciones  # tabla `evaluaciones` (mejor esfuerzo) además del archivo
        from datetime import date
        tabla_evaluaciones.subir(tabla_evaluaciones.filas_anonimizador(salida, date.today().isoformat(), "desconocido"))
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
