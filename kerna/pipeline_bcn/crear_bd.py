"""
Crea (o actualiza) la base MongoDB del corpus normativo: colecciones, validación
de esquema e índices. Idempotente: se puede correr las veces que se quiera.

Uso:
  set -a && . ./.env && set +a
  python3 crear_bd.py --probar     # solo prueba conexión y permisos, no crea nada
  python3 crear_bd.py              # crea/actualiza colecciones, validadores e índices

Requiere MONGODB_URI con el nombre de la base en la ruta, p. ej.
  mongodb+srv://kerna_app:<clave>@cluster0.xxxxx.mongodb.net/kerna?retryWrites=true&w=majority
y un usuario con roles readWrite + dbAdmin sobre esa base.
"""
from __future__ import annotations

import argparse
import os
import sys

from extraer_bcn import asegurar_indices

_STR = {"bsonType": "string"}
_BOOL = {"bsonType": "bool"}
_ARR_STR = {"bsonType": "array", "items": {"bsonType": "string"}}

# Validación "moderate": aplica a inserciones y a documentos que ya la cumplen.
ESQUEMAS = {
    "normas": {
        "required": ["_id", "clave", "id_norma", "nombre_corto", "fuente", "hash_fuente",
                     "vigente", "vigencia_anticipada", "extraido_en"],
        "properties": {
            "_id": _STR, "clave": _STR, "id_norma": {"bsonType": ["int", "long"]},
            "nombre_corto": _STR, "fuente": {"enum": ["xml", "json"]},
            "hash_fuente": _STR, "vigente": _BOOL, "vigencia_anticipada": _BOOL,
            "politica_vigencia": {"enum": ["bcn", "anticipada", "historica"]},
            "categorias": _ARR_STR,
        },
    },
    "fragmentos": {
        "required": ["_id", "clave_corpus", "id_norma", "norma", "articulo", "jerarquia", "texto",
                     "texto_embedding", "tipo_contenido", "vigente", "vigencia_anticipada",
                     "estado_embedding", "hash_texto", "url_fuente"],
        "properties": {
            "_id": _STR, "clave_corpus": _STR, "id_norma": {"bsonType": ["int", "long"]},
            "norma": _STR, "articulo": _STR, "jerarquia": _ARR_STR,
            "texto": {"bsonType": "string", "minLength": 1},
            "texto_embedding": {"bsonType": "string", "minLength": 1},
            "tipo_contenido": {"enum": ["sustantiva", "modificatoria", "promulgatoria"]},
            "vigente": _BOOL, "vigencia_anticipada": _BOOL, "transitorio": _BOOL,
            "estado_embedding": {"enum": ["pendiente", "ok", "no_aplica"]},
            "categorias": _ARR_STR, "modificado_por": _ARR_STR,
        },
    },
    "normas_historial": {"required": ["_id", "clave", "archivada_en"], "properties": {}},
    "fragmentos_historial": {"required": ["_id", "fragmento_id", "archivado_en"], "properties": {}},
}


def conectar():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        sys.exit("Falta MONGODB_URI (cargar .env: set -a && . ./.env && set +a)")
    from pymongo import MongoClient
    from pymongo.errors import ConfigurationError
    from pymongo.errors import InvalidURI
    try:
        cliente = MongoClient(uri, serverSelectionTimeoutMS=15000)
    except InvalidURI as e:
        # El mensaje del driver puede incluir la URI con la clave: no se muestra.
        sys.exit(f"URI inválida ({type(e).__name__}). Formato esperado: "
                 "mongodb+srv://USUARIO:CLAVE@host/kerna?retryWrites=true&w=majority")
    try:
        db = cliente.get_default_database()
    except ConfigurationError:
        sys.exit("La URI no trae el nombre de la base: agregar /kerna antes del '?'")
    return cliente, db


def probar(cliente, db) -> bool:
    cliente.admin.command("ping")
    print(f"OK conexión a {cliente.address or 'cluster'} — base '{db.name}'")
    estado = db.command("connectionStatus", showPrivileges=True)["authInfo"]
    roles = {(r["role"], r["db"]) for r in estado.get("authenticatedUserRoles", [])}
    print("Roles:", sorted(roles) or "(sin info)")
    acciones = {a for p in estado.get("authenticatedUserPrivileges", [])
                if p.get("resource", {}).get("db") in (db.name, "")
                for a in p.get("actions", [])}
    faltan = {"insert", "update", "find", "createIndex", "createCollection", "collMod"} - acciones
    if acciones and faltan:
        print("FALTAN permisos sobre la base:", sorted(faltan),
              "→ dar al usuario readWrite + dbAdmin sobre", db.name)
        return False
    print("Permisos suficientes." if acciones else
          "No se pudieron leer los privilegios; se verificará al crear.")
    return True


def crear(db):
    existentes = set(db.list_collection_names())
    for nombre, esquema in ESQUEMAS.items():
        validador = {"$jsonSchema": {"bsonType": "object", **esquema}}
        if nombre in existentes:
            db.command("collMod", nombre, validator=validador, validationLevel="moderate",
                       validationAction="error")
            print(f"actualizada  {nombre}")
        else:
            db.create_collection(nombre, validator=validador, validationLevel="moderate",
                                 validationAction="error")
            print(f"creada       {nombre}")
    asegurar_indices(db)
    for nombre in ESQUEMAS:
        idx = sorted(i["name"] for i in db[nombre].list_indexes())
        print(f"índices      {nombre}: {idx}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--probar", action="store_true", help="solo probar conexión y permisos")
    args = ap.parse_args()
    cliente, db = conectar()
    ok = probar(cliente, db)
    if args.probar:
        return 0 if ok else 1
    if not ok:
        return 1
    crear(db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
