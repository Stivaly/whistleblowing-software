"""Ubicación del cuestionario de Veridy con listas oficiales de Chile: País → Región → Comuna.

Convierte los campos de texto del paso de ubicación («País», «Estado/Provincia», «Ciudad/Comuna») en listas:
País (Chile), Región (16, de norte a sur; aparece al elegir Chile) y Comuna (una lista por región, en orden
alfabético; solo se ve la de la región elegida). Nada se borra: los campos existentes se convierten y las
comunas de las otras regiones se agregan como campos nuevos. Las denuncias anteriores conservan su propia copia
del cuestionario, así que se siguen viendo igual.

Corre dentro del contenedor de Veridy (tiene sqlalchemy y acceso a la base):
  docker exec -i -e CHILE_JSON="$(cat entregable/herramientas/chile_regiones_comunas.json)" veridy-kerna-veridy-1 \
    python3 - < entregable/herramientas/ubicacion_chile.py
Imprime primero un respaldo JSON (línea que empieza con RESPALDO) y luego el resultado.
Idempotente: si Región ya es una lista, no hace nada.
"""
import json
import os
import uuid

from sqlalchemy import create_engine, text

PASO = "c498e190-1c09-4174-ad1f-623d6c6c700b"
PAIS, REGION, COMUNA = ("b60e0687-06e4-4e94-9037-add4a0bc9a98", "61d5c2eb-fc33-4417-a601-b3a9abc3707a",
                        "cdd750f2-aa87-4511-8dfb-8d3cef45f36e")
AREA, FECHA = "0123d6bf", "353cd283"
CHILE = json.loads(os.environ["CHILE_JSON"])  # {"regiones": [{"nombre", "comunas": [...]}, ...]}


def es(t: str) -> str:
    return json.dumps({"es": t})


def main() -> None:
    uri = f"postgresql+psycopg2://veridy_app@{os.environ['VERIDY_PG_FQDN']}:5432/veridy?sslmode=verify-full&sslrootcert=system"
    with create_engine(uri).begin() as c:
        q = lambda sql, **k: c.execute(text(sql), k)
        respaldo = {
            "field": [dict(r) for r in q("select * from field where step_id=:p", p=PASO).mappings()],
            "fieldoption": [dict(r) for r in q("select o.* from fieldoption o join field f on f.id=o.field_id where f.step_id=:p", p=PASO).mappings()],
            "fieldattr": [dict(r) for r in q("select a.* from fieldattr a join field f on f.id=a.field_id where f.step_id=:p", p=PASO).mappings()],
        }
        print("RESPALDO " + json.dumps(respaldo, default=str, ensure_ascii=False))
        if q("select type from field where id=:i", i=REGION).scalar() == "selectbox":
            print("ya aplicado: no se cambia nada")
            return

        def lista(campo: str, etiqueta: str, y: int, opciones: list[str], alfabetico: bool) -> list[str]:
            q("update field set type='selectbox', label=:l, y=:y, x=0, width=0 where id=:i", l=es(etiqueta), y=y, i=campo)
            v = "true" if alfabetico else "false"
            if q("update fieldattr set value=:v where field_id=:i and name='display_alphabetically'", v=v, i=campo).rowcount == 0:
                q("insert into fieldattr (field_id, name, type, value) values (:i, 'display_alphabetically', 1, :v)", i=campo, v=v)
            ids = []
            for n, o in enumerate(opciones):
                oid = str(uuid.uuid4()); ids.append(oid)
                q("insert into fieldoption (id, field_id, \"order\", label, hint1, hint2, score_points, score_type, block_submission, trigger_receiver)"
                  " values (:id, :f, :n, :l, :h, :h, 0, 1, false, '[]')", id=oid, f=campo, n=n, l=es(o), h=es(""))
            return ids

        def disparar(opcion: str, campo: str) -> None:
            q("insert into fieldoptiontriggerfield (option_id, object_id, sufficient) values (:o, :c, true)", o=opcion, c=campo)

        (chile,) = lista(PAIS, "País", 0, ["Chile"], False)
        regiones = lista(REGION, "Región", 1, [r["nombre"] for r in CHILE["regiones"]], False)
        disparar(chile, REGION)
        for n, (r, opcion) in enumerate(zip(CHILE["regiones"], regiones)):
            if n == 0:
                campo = COMUNA
            else:
                campo = str(uuid.uuid4())
                q("insert into field (id, tid, x, y, width, label, description, hint, placeholder, required, multi_entry,"
                  " triggered_by_score, step_id, fieldgroup_id, type, instance, template_id, template_override_id)"
                  " values (:id, 1, 0, 2, 0, :l, :v, :v, :v, true, false, 0, :p, null, 'selectbox', 0, null, null)",
                  id=campo, l=es("Comuna"), v=es(""), p=PASO)
            lista(campo, "Comuna", 2 + n, r["comunas"], False)  # una fila por lista (las ocultas no angostan la visible); ya vienen en orden alfabético español (la Ñ tras la N)
            disparar(opcion, campo)
        q("update field set y=18 where step_id=:p and id like :a", p=PASO, a=AREA + "%")
        q("update field set y=19 where step_id=:p and id like :f", p=PASO, f=FECHA + "%")
        print(f"listo: País, Región ({len(regiones)}) y Comuna ({sum(len(r['comunas']) for r in CHILE['regiones'])} en {len(regiones)} listas)")


if __name__ == "__main__":
    main()
