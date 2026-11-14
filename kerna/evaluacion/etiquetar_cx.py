"""Agrega etiquetas manuales (CX-xxxx) a datos/cx_etiquetas.jsonl y arma el archivo de casos etiquetados.

Uso: python3 etiquetar_cx.py agregar <archivo_con_lineas>   líneas: ID|triage|confianza|ley|sec|arts|justificación
     python3 etiquetar_cx.py construir                       escribe denuncias_complejas_20261114_etiquetadas.json
Abreviaturas de artículo: CT:2, DP:12 (19.628/21.719), PJ:1 (20.393), 18575:62, EA:84, EM:82, LOCM:76, 21643:6.
Sin LLM: las etiquetas las escribe una persona leyendo cada relato; aquí solo se validan contra el corpus y se arma el JSON.
"""
import json
import sys
from pathlib import Path

DATOS = Path(__file__).parent / "datos"
ORIGEN = DATOS / "denuncias_complejas_20261114_auditadas.json"
ETIQ = DATOS / "cx_etiquetas.jsonl"
SALIDA = DATOS / "denuncias_complejas_20261114_etiquetadas.json"
CORPUS = DATOS / "corpus_articulos.json"   # ids de artículo vigentes (181), volcados de Qdrant
PREFIJO = {"CT": "207436-karin", "DP": "141599-2026-12-01", "PJ": "1008668", "18575": "191865-karin",
           "EA": "236392-karin", "EM": "30256-karin", "LOCM": "251693-karin", "21643": "1200096"}
TRIAGE = ("si", "control", "no")
CONFIANZA = ("alta", "media", "baja")
LEYES = ("21.643", "20.393", "19.628-21.719", "18.575-18.834-18.883", "ninguna")
LEY_DE = {"207436-karin": "21.643", "1200096": "21.643", "141599-2026-12-01": "19.628-21.719",
          "1209272": "19.628-21.719", "1008668": "20.393", "191865-karin": "18.575-18.834-18.883",
          "236392-karin": "18.575-18.834-18.883", "30256-karin": "18.575-18.834-18.883",
          "251693-karin": "18.575-18.834-18.883"}
CRITERIO = ("Casos sintéticos complejos auditados (B6, 2026-11-14), etiquetados a mano uno por uno. triage: si = algún "
            "artículo del corpus vigente aplica a la conducta (norma chilena); control = no hay falta; no = hay una "
            "falta cuya norma está fuera del corpus (se excluye de la medición). articulos_corregidos = etiqueta "
            "final (IDs de fragmento sin -pN). Mismos campos que prueba3; particion: afinar | medir_complejas.")


def art_id(abrev: str) -> str:
    cuerpo, num = abrev.strip().split(":")
    return f"{PREFIJO[cuerpo]}-art-{num.strip().lower()}"


def validar(fila: dict, corpus: set[str] | None) -> None:
    assert fila["triage"] in TRIAGE and fila["confianza"] in CONFIANZA and fila["ley"] in LEYES, fila["id"]
    if fila["triage"] == "si":
        assert fila["arts"] and fila["ley"] != "ninguna", fila["id"]
    else:
        assert not fila["arts"] and fila["ley"] == "ninguna", fila["id"]
    if corpus is not None:
        malos = [a for a in fila["arts"] if a not in corpus]
        assert not malos, (fila["id"], malos)
    if fila["arts"]:
        assert ley_de_articulo(fila["arts"][0]) == fila["ley"], (fila["id"], "la ley principal es la del primer artículo")


def ley_de_articulo(art: str) -> str:
    return next(ley for pref, ley in LEY_DE.items() if art.startswith(pref + "-art-"))


def parsear(linea: str) -> dict:
    id_, triage, conf, ley, sec, arts, just = [p.strip() for p in linea.split("|", 6)]
    arts_ids = [art_id(a) for a in arts.split(",") if a.strip()]
    sec = ";".join(dict.fromkeys(x for x in map(ley_de_articulo, arts_ids) if x != ley))   # leyes de los artículos
    return {"id": id_, "triage": triage, "confianza": conf, "ley": ley, "sec": sec, "arts": arts_ids, "just": just}


def cargar_corpus() -> set[str] | None:
    return set(json.loads(CORPUS.read_text())) if CORPUS.exists() else None


def agregar(ruta: str) -> None:
    corpus = cargar_corpus()
    previas = {json.loads(x)["id"] for x in ETIQ.read_text().splitlines()} if ETIQ.exists() else set()
    nuevas = [parsear(x) for x in Path(ruta).read_text().splitlines() if x.strip() and not x.startswith("#")]
    for f in nuevas:
        validar(f, corpus)
        assert f["id"] not in previas, f"{f['id']} ya etiquetado"
    with ETIQ.open("a") as fh:
        for f in nuevas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print(f"{len(nuevas)} etiquetas agregadas; total {len(previas) + len(nuevas)}")


def construir_caso(c: dict, e: dict) -> dict:
    n = c["id"].split("-")[1]
    arts = e["arts"]
    return {"id": c["id"], "fuente_tipo": "sintetica", "plataforma_o_sitio": "Denuncia sintética compleja (2026-11-14)",
            "subreddit_o_seccion": "", "url": "", "url_archivo": "", "fecha_publicacion": "2026-11-14",
            "fecha_consulta": "2026-11-14", "pais": "", "evidencia_pais": "", "autor_pseudonimo": f"C-{n}",
            "titulo": "", "resumen_parafraseado": "", "ley_principal": e["ley"], "leyes_secundarias": e["sec"],
            "articulos_candidatos": "", "submateria": "", "rol_denunciante": "",
            "es_caso_frontera": "sí" if e["confianza"] == "baja" or e["triage"] == "control" else "no",
            "por_que_frontera": e["just"] if e["confianza"] == "baja" else "",
            "largo_caracteres": len(c["texto_original"]), "calidad_para_eval": "alta", "motivo_calidad": "",
            "pii_en_texto": "sin catalogar (texto sin anonimizar)", "apto_triggers_anonimizador": "por revisar",
            "resolucion_conocida": "No aplica (relato sintético).",
            "notas": "Etiquetado a mano por criterio jurídico, leyendo el relato completo, sin LLM; ver justificacion_juridica.",
            "texto_original": c["texto_original"], "triage": e["triage"], "confianza": e["confianza"],
            "justificacion_juridica": e["just"], "particion": c["particion"], "articulos_corregidos": arts,
            "articulos_corpus": arts, "cambios_etiqueta": []}


def construir() -> None:
    casos = json.loads(ORIGEN.read_text())
    etiq = {json.loads(x)["id"]: json.loads(x) for x in ETIQ.read_text().splitlines()}
    salida = [construir_caso(c, etiq[c["id"]]) for c in casos if c["id"] in etiq]
    SALIDA.write_text(json.dumps({"generado": "2026-11-14", "criterio": CRITERIO, "casos": salida},
                                 ensure_ascii=False, indent=1))
    print(f"{len(salida)} de {len(casos)} casos escritos en {SALIDA.name}")


if __name__ == "__main__":
    if sys.argv[1] == "agregar":
        agregar(sys.argv[2])
    else:
        construir()
