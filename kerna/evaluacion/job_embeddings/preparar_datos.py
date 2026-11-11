"""Exporta los datos que van DENTRO de la imagen del job (el ACR es privado):

  datos/fragmentos.json          fragmentos vigentes sustantivos de Mongo: [{id, texto_embedding, payload}]
                                 (id y payload exactamente como los sube embed_sync.py)
  datos/denuncias_publicas.json  copia del dataset de consultas

Lo invoca preparar_datos.sh, que abre y cierra el acceso temporal a Atlas. Requiere MONGODB_URI.
"""
import json
import os
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
KERNA = AQUI.parents[1]
sys.path.insert(0, str(KERNA / "pipeline_bcn"))
import embed_sync  # noqa: E402


def main():
    from pymongo import MongoClient

    db = MongoClient(os.environ["MONGODB_URI"]).get_default_database()
    filas = [{"id": embed_sync.punto_id(f["_id"]), "texto_embedding": f["texto_embedding"],
              "payload": embed_sync.payload_de(f)}
             for f in db.fragmentos.find({"vigente": True, "estado_embedding": {"$ne": "no_aplica"}}).sort("_id", 1)]
    if not filas:
        raise SystemExit("Mongo no devolvió fragmentos vigentes")
    (AQUI / "datos").mkdir(exist_ok=True)
    (AQUI / "datos" / "fragmentos.json").write_text(json.dumps(filas, ensure_ascii=False), encoding="utf-8")
    shutil.copyfile(KERNA / "evaluacion" / "datos" / "denuncias_publicas.json",
                    AQUI / "datos" / "denuncias_publicas.json")
    print(f"Exportados {len(filas)} fragmentos vigentes y el dataset a {AQUI / 'datos'}")


if __name__ == "__main__":
    main()
