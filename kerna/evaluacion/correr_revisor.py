"""
Corre la cadena del núcleo (con la configuración KERNA_* del entorno, p. ej. KERNA_REVISOR=1) sobre los casos del
triage de una partición y arma el JSON de casos que lee `medir_revisor.py`. No guarda textos de denuncias.

Cada caso: texto_original anonimizado (como entrega el conector), etiqueta corregida del triage como esperados
(nivel artículo; las sugerencias se normalizan a artículo quitando -pN), control = caso `control` del triage.
Modelo de lenguaje: Azure OpenAI (por defecto gpt-5-nano) en un solo nivel de la cadena.

Uso (desde kerna/):
  set -a; . pipeline_bcn/.env; set +a      # más AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_KEY
  KERNA_REVISOR=1 KERNA_EVALUADOR=1 ... PYTHONPATH=nucleo:comun:pipeline_bcn python3 evaluacion/correr_revisor.py \
      --particion desarrollo --salida evaluacion/registro/casos_revisor_desarrollo.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "nucleo"))
sys.path.insert(0, str(AQUI.parent / "comun"))
import recall_retriever as rr  # noqa: E402
from kerna_comun import anonimizador  # noqa: E402
from kerna_nucleo.almacen import AlmacenMemoria  # noqa: E402
from kerna_nucleo.api import proveedores_reales  # noqa: E402
from kerna_nucleo.config import Config  # noqa: E402
from kerna_nucleo.enrutador import Enrutador, Nivel  # noqa: E402
from kerna_nucleo.orquestador import Orquestador  # noqa: E402
from kerna_nucleo.retriever import Retriever  # noqa: E402

TRIAGE = AQUI / "datos" / "triage_casos.json"


def construir(c: Config, modelo: str):
    prov = proveedores_reales(c)
    enr = Enrutador([Nivel("oficial", "azure-openai", modelo)], prov.gemini, plazo_global=c.plazo_global_s,
                    corte=c.corte_llamada_s, esperas=(30.0, 60.0, 120.0), umbral_fallas=10**6,
                    clientes={"azure-openai": prov.azure_openai})
    ret = Retriever(prov.voyage, prov.qdrant, prov.local, c.coleccion, c.embedding,
                    max(c.top_k, c.evaluador_candidatos) if c.evaluador else c.top_k, c.umbral_similitud,
                    rerank_modelo=c.rerank_modelo, rerank_candidatos=c.rerank_candidatos, hibrida=c.hibrida,
                    hibrida_profundidad=c.hibrida_profundidad, hibrida_stemming=c.hibrida_stemming,
                    multiquery_relato=c.multiquery_relato, peso_relato=c.multiquery_peso_relato,
                    extras_fusion=c.hibrida_extras)
    alm = AlmacenMemoria()
    return alm, Orquestador(c, alm, enr, ret, time.time)


async def correr(casos: list[dict], triage: dict, c: Config, modelo: str) -> list[dict]:
    alm, orq = construir(c, modelo)
    out: list[dict] = []

    async def uno(caso: dict):
        t = triage[caso["id"]]
        texto = anonimizador.anonimizar(rr.texto_consulta(caso, "texto_original")).texto
        sol = {"id_solicitud": str(uuid.uuid4()), "cliente": "eval", "ref_opaca": str(uuid.uuid4()),
               "id_empresa": "eval", "estado": "pendiente", "creada_en": time.time()}
        sol, _ = await alm.crear_solicitud(sol)
        await orq.procesar(sol, texto)
        fin = await alm.obtener_solicitud("eval", sol["ref_opaca"])
        arts = await alm.listar_articulos(sol["id_solicitud"]) if fin["estado"] == "completada" else []
        por_art: dict[str, dict] = {}
        for a in arts:
            idart = rr.articulo_de(a["id_articulo"])
            if idart not in por_art or a["confianza"] > por_art[idart]["confianza"]:
                por_art[idart] = {**a, "id_articulo": idart}
        control = t["en_alcance"] == "control"
        out.append({"id": caso["id"], "control": control, "ley": caso["ley_principal"],
                    "esperados": [] if control else sorted(t["articulos_corregidos"]),
                    "estado": fin["estado"], "motivo_revision": fin.get("motivo_revision"),
                    "revision_juridica": fin.get("revision_juridica"), "alertas_revision": fin.get("alertas_revision"),
                    "tokens_entrada": fin.get("tokens_entrada"), "tokens_salida": fin.get("tokens_salida"),
                    "sugerencias": [{k: a.get(k) for k in ("id_articulo", "confianza", "dictamen", "causal_veto",
                                                           "condiciones", "confianza_revisor", "revision_juridica")}
                                    for a in por_art.values()]})
        print(f"{caso['id']}: {fin['estado']} {len(por_art)} sugerencias ({fin.get('revision_juridica')})", flush=True)

    await asyncio.gather(*(uno(x) for x in casos))
    return sorted(out, key=lambda x: x["id"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", required=True, choices=["desarrollo", "prueba"])
    ap.add_argument("--salida", required=True)
    ap.add_argument("--modelo", default="gpt-5-nano")
    ap.add_argument("--reanudar", metavar="JSON", help="repite solo los casos con cadena_agotada de una corrida previa y la completa")
    ap.add_argument("--limite", type=int, help="solo los primeros N casos (humo)")
    a = ap.parse_args(argv)
    c = Config.desde_entorno()
    triage = {e["id"]: e for e in json.loads(TRIAGE.read_text())["casos"]}
    casos = [x for x in json.loads(rr.DATASET.read_bytes())["casos"]
             if triage[x["id"]]["particion"] == a.particion and triage[x["id"]]["en_alcance"] in ("si", "control")]
    previo: list[dict] = []
    if a.reanudar:
        previo = json.loads(Path(a.reanudar).read_text())
        malos = {x["id"] for x in previo if x["motivo_revision"] in ("cadena_agotada", "tiempo_agotado")}
        previo = [x for x in previo if x["id"] not in malos]
        casos = [x for x in casos if x["id"] in malos]
    if a.limite:
        casos = casos[: a.limite]
    print(f"{a.particion}: {len(casos)} casos; hibrida={c.hibrida} multiquery={c.multiquery} evaluador={c.evaluador} "
          f"revisor={c.revisor} concurrencia={c.concurrencia} modelo={a.modelo}", flush=True)
    res = sorted(previo + asyncio.run(correr(casos, triage, c, a.modelo)), key=lambda x: x["id"])
    Path(a.salida).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("casos escritos:", a.salida)


if __name__ == "__main__":
    main()
