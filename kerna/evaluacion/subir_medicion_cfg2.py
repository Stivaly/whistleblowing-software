"""Sube a la tabla `evaluaciones` la medición de desarrollo de la configuración del exp. 2 (salida de operaciones/medicion_config_exp2.sh).
Escribe recall@5 por artículo de la cadena + revisor (global y por ley, con IC 95 %), solo agregados.
Uso: python3 evaluacion/subir_medicion_cfg2.py evaluacion/registro/cfg2-r1-desarrollo-20261114.json [--escribir]
Sin --escribir solo muestra las filas. La marca `vigente` se escribe aparte (kerna/front/README.md)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tabla_evaluaciones as t  # noqa: E402

CONFIG = ("cadena completa (evaluador 3m, 70 candidatos, híbrida +15, multiquery 3, BM25 concat, colección normativa_cl_x_e) + "
          "completar top 5 + reranker LLM (ventana 35, votos 2/2, 2 permutaciones, gpt-5-nano) + revisor")

ap = argparse.ArgumentParser()
ap.add_argument("archivo", type=Path)
ap.add_argument("--escribir", action="store_true")
a = ap.parse_args()
d = json.loads(a.archivo.read_text())
sd = d["sets"]["desarrollo"]["cadena"]
filas = []
for ley, m in sd.items():
    r = m["revisor5"]
    amb = "global" if ley == "global" else ley
    filas.append(t.fila("recall_retriever", d["fecha"], d["commit"], "recall5", r["valor"], amb,
                        {"particion": "desarrollo", "coleccion": d["coleccion"], "configuracion": CONFIG, "meta": 0.8,
                         "dataset_casos": sd["global"]["revisor5"]["n"], "corpus_articulos": d["corpus_articulos"],
                         "campo_consulta": "texto_original", "evaluador_resumen": {"cadena": "3m"}},
                        {"casos": r["n"], "casos_articulo": r["n"], "ic95_inf": r["ic95"][0], "ic95_sup": r["ic95"][1]}))
for f in filas:
    print(f["ambito"], f["valor"], f["detalle"])
if a.escribir:
    print("filas escritas:", t.subir(filas), "fecha:", d["fecha"])
