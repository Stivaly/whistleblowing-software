"""Lee los resultados de medición de la tabla `evaluaciones` (Azure Table Storage de Kerna) y arma el modelo de
calidad que usa el informe. Identidad administrada del App Service (rol Storage Table Data Reader sobre la tabla).
Sin texto ni identificadores: solo agregados. Si la tabla está vacía o no responde, devuelve None (el informe dice «sin datos»).
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict

TABLA = "evaluaciones"
SET = "desarrollo"  # el panel muestra siempre este set (casos reales y complejos); los demás sets no van al panel
_cache: dict = {"t": 0.0, "v": None}
TTL_S = 120


def _tabla():
    from azure.data.tables import TableClient
    from azure.identity import DefaultAzureCredential
    return TableClient(endpoint=os.environ["EVALUACIONES_TABLA_URL"], table_name=TABLA, credential=DefaultAzureCredential())


def _j(x) -> dict:
    try:
        v = json.loads(x) if isinstance(x, str) else (x or {})
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def leer_filas(tabla=None) -> list[dict]:
    tabla = tabla or _tabla()
    return [dict(e) for e in tabla.list_entities()]


def _ultima(filas, fuente):
    f = [x for x in filas if x.get("PartitionKey") == fuente]
    if not f:
        return []
    corte = max(x["fecha"] for x in f)
    return [x for x in f if x["fecha"] == corte]


def _desarrollo(filas: list[dict]) -> list[dict]:
    """Filas de recall del set desarrollo medidas con la configuración vigente (la desplegada en Veridy).
    La marca es la fila `vigente`/`desarrollo` de la tabla (campo `corrida` = fecha de la medición); sin marca, la última medición de desarrollo sobre `normativa_cl`."""
    rec = [x for x in filas if x.get("PartitionKey") == "recall_retriever" and _j(x.get("parametros")).get("particion") == SET]
    marca = next((x.get("corrida") for x in filas if x.get("PartitionKey") == "vigente" and x.get("RowKey") == SET), None)
    if marca:
        return [x for x in rec if x["fecha"] == marca]
    prod = [x for x in rec if _j(x.get("parametros")).get("coleccion") == "normativa_cl"]
    corte = max((x["fecha"] for x in prod), default=None)
    return [x for x in prod if x["fecha"] == corte]


def construir(filas: list[dict]) -> dict | None:
    """Reconstruye {recall, serie, corpus_articulos, evaluador, anonimizador, pruebas, precios_embeddings}."""
    if not filas:
        return None
    out: dict = {}
    dev = [x for x in _desarrollo(filas) if x.get("metrica") == "recall5"]
    if dev:
        ult = dev
        corridas = defaultdict(list)
        for x in filas:
            p = _j(x.get("parametros"))
            if x.get("PartitionKey") == "recall_retriever" and x.get("metrica") == "recall5" and p.get("particion") == SET and p.get("coleccion") == "normativa_cl":
                corridas[x["fecha"]].append(x)
        corridas[ult[0]["fecha"]] = ult
        fechas = sorted(corridas)
        glob = next((x for x in ult if x["ambito"] == "global"), ult[0])
        par = _j(glob.get("parametros"))
        por_ley = []
        for x in ult:
            d = _j(x.get("detalle"))
            por_ley.append({"ley": "Global" if x["ambito"] == "global" else x["ambito"], "casos": d.get("casos"),
                            "casos_articulo": d.get("casos_articulo"), "recall_ley": d.get("recall_ley"), "recall5": x.get("valor"),
                            "ic95_inf": d.get("ic95_inf"), "ic95_sup": d.get("ic95_sup")})
        por_ley.sort(key=lambda z: (z["ley"] != "Global", z["ley"]))
        out["recall"] = {"fecha": ult[0]["fecha"], "set": SET, "commit": glob.get("commit"), "configuracion": par.get("configuracion"),
                         "meta": par.get("meta", 0.8), "dataset_casos": par.get("dataset_casos"), "por_ley": por_ley,
                         "fuente": "tabla evaluaciones (recall_retriever)"}
        out["serie"] = []
        for f in fechas:
            g = next((x for x in corridas[f] if x["ambito"] == "global"), None)
            p = _j(g.get("parametros")) if g else {}
            if g and (p.get("campo_consulta") == "texto_original" or p.get("evaluador_resumen")):
                out["serie"].append({"fecha": f[:16].replace("T", " "), "configuracion": p.get("configuracion"), "recall5": g.get("valor")})
        out["corpus_articulos"] = par.get("corpus_articulos")
        out["evaluador"] = par.get("evaluador_resumen") or None
    anon = _ultima(filas, "anonimizador")
    if anon:
        tipos, apar = [], []
        for x in sorted(anon, key=lambda z: z["ambito"]):
            d = _j(x.get("detalle"))
            if x["metrica"] == "recall_por_caso":
                tipos.append({"tipo": x["ambito"], "casos_con_dato": d.get("casos_con_dato"), "casos_detectados": d.get("casos_detectados"),
                              "recall_por_caso": None if x.get("valor") is None else round(x["valor"], 3)})
            elif x["metrica"] == "ocultas":
                apar.append({"tipo": x["ambito"], "total": d.get("total"), "ocultas": d.get("ocultas")})
        out["anonimizador"] = {"fecha": anon[0]["fecha"], "casos": _j(anon[0].get("parametros")).get("casos"), "tipos": tipos,
                               "apariciones": apar, "fuente": "tabla evaluaciones (anonimizador)"}
    pr = _ultima(filas, "pruebas")
    if pr:
        out["pruebas"] = {"fecha": pr[0]["fecha"], "commit": pr[0].get("commit"),
                          "capas": {x["ambito"]: _j(x.get("detalle")) for x in pr}, "fuente": "tabla evaluaciones (pruebas)"}
    precios = _ultima(filas, "precios_embeddings")
    if precios:
        out["precios_embeddings"] = {x["ambito"]: x.get("valor") for x in precios}
    if not out:
        return None
    out["generado"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    return out


def cargar(tabla=None, cache: bool = True) -> dict | None:
    """Datos de evaluación en vivo. Lanza si la tabla no responde (el informe lo declara)."""
    ahora = time.monotonic()
    if cache and tabla is None and _cache["v"] is not None and ahora - _cache["t"] < TTL_S:
        return _cache["v"]
    v = construir(leer_filas(tabla))
    if tabla is None:
        _cache.update(t=ahora, v=v)
    return v
