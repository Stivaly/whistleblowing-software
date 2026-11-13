"""Genera el enriquecimiento de los artículos del corpus (experimento KERNA_ENRIQUECIDO).

Por artículo, con un LLM por API y SOLO desde el texto legal (nunca se leen casos de evaluación ni el corpus completo
en un pedido): `rol` (sustantivo | sancion | procedimiento | definicion | vigencia) y 3 a 6 `hechos` típicos en
lenguaje común que harían aplicable el artículo; en artículos-lista (ver fragmentar_literales) además 1 a 3 hechos por
literal. El resultado se versiona en `enriquecimiento_articulos.json` (clave: id de artículo sin sufijo -pN).

Uso (desde kerna/; credenciales de Key Vault con operaciones/correr_evaluacion.sh):
  operaciones/correr_evaluacion.sh python3 pipeline_bcn/enriquecer_articulos.py --fragmentos fragmentos.json
  (fragmentos.json: volcado de los payloads vigentes de la colección, ver operaciones/volcar_fragmentos.sh)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "nucleo"))
sys.path.insert(0, str(AQUI.parent / "comun"))
from fragmentar_literales import partir_literales  # noqa: E402

SALIDA = AQUI / "enriquecimiento_articulos.json"
ROLES = ["sustantivo", "sancion", "procedimiento", "definicion", "vigencia"]
MODELO = "gpt-5-mini"

SISTEMA = (
    "Eres un analista jurídico chileno. Recibes UN artículo de una norma y lo describes para un buscador. "
    "Usa solo el texto recibido; no agregues leyes, artículos ni hechos que el texto no sustente.\n"
    "1. rol (uno): sustantivo = establece una obligación, prohibición, derecho o conducta que se puede cumplir o "
    "infringir; sancion = fija penas, multas, infracciones o consecuencias de haber infringido; procedimiento = regula "
    "plazos, trámites, competencia, órganos o cómo se tramita o prueba algo; definicion = define términos o conceptos; "
    "vigencia = aplicación en el tiempo, ámbito de aplicación, disposiciones finales o de remisión. Si el artículo enumera las conductas, delitos o supuestos que generan responsabilidad u obligaciones, es sustantivo aunque mencione el procedimiento.\n"
    "2. hechos: entre 3 y 6 situaciones concretas, en lenguaje cotidiano, como las contaría una persona sin formación "
    "jurídica que vivió o presenció algo que haría aplicable este artículo (\"mi jefe me grita delante de todos\", "
    "\"la empresa vendió mis datos sin avisarme\"). Una frase corta cada una, sin citar números de artículo ni "
    "nombres de leyes, sin jerga jurídica. Si el artículo es de procedimiento, definición o vigencia, describe los "
    "hechos o consultas en que esa regla importa (p. ej. quien pregunta hasta cuándo puede reclamar).\n"
    "3. literales: solo si recibes el artículo dividido en literales, para cada literal (por su etiqueta) 1 a 3 hechos "
    "típicos concretos de ese literal; si no, un objeto vacío.\n"
    "Responde solo JSON: {\"rol\": ..., \"hechos\": [...], \"literales\": {\"a\": [...]}}."
)


def articulos(fragmentos: list[dict]) -> dict[str, dict]:
    """Agrupa los fragmentos vigentes por artículo (une las partes -pN en orden)."""
    por: dict[str, list[dict]] = {}
    for f in fragmentos:
        por.setdefault(re.sub(r"-p\d+$", "", f["fragmento_id"]), []).append(f)
    out = {}
    for aid, fr in sorted(por.items()):
        fr.sort(key=lambda f: f["fragmento_id"])
        out[aid] = {"norma": fr[0]["norma"], "articulo": fr[0]["articulo"], "partes": len(fr),
                    "texto": "\n\n".join(f["texto"] for f in fr)}
    return out


def esquema() -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["rol", "hechos", "literales"],
            "properties": {"rol": {"type": "string", "enum": ROLES},
                           "hechos": {"type": "array", "items": {"type": "string"}},
                           "literales": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}}}}


def usuario(a: dict) -> str:
    intro, lits = partir_literales(a["texto"]) if a["partes"] == 1 else (a["texto"], [])
    cab = f"Norma: {a['norma']}. Artículo {a['articulo']}.\n"
    if not lits:
        return cab + "\nTexto:\n" + a["texto"]
    return cab + "\nIntroducción: " + intro + "\n\nLiterales:\n" + "\n".join(f"[{e}] {t}" for e, t in lits)


def validar(r: dict, a: dict) -> dict:
    if r.get("rol") not in ROLES:
        raise ValueError("rol")
    hechos = [str(h).strip() for h in r.get("hechos", []) if str(h).strip()][:6]
    if len(hechos) < 3:
        raise ValueError("hechos")
    _, lits = partir_literales(a["texto"]) if a["partes"] == 1 else ("", [])
    esperadas = {e for e, _ in lits}
    literales = {k: [str(h).strip() for h in v if str(h).strip()][:3] for k, v in (r.get("literales") or {}).items()
                 if k in esperadas}
    if esperadas - {k for k, v in literales.items() if v}:
        raise ValueError("literales")
    return {"rol": r["rol"], "hechos": hechos, **({"literales": literales} if literales else {})}


async def generar(frags: list[dict], modelo: str, salida: Path, solo: list[str] | None) -> None:
    from kerna_nucleo.proveedores.azure_openai import ClienteAzureOpenAI
    cli = ClienteAzureOpenAI(os.environ["AZURE_OPENAI_ENDPOINT"], os.environ["AZURE_OPENAI_KEY"], esfuerzo="low")
    arts = articulos(frags)
    previo = json.loads(salida.read_text())["articulos"] if salida.exists() else {}
    sem = asyncio.Semaphore(6)
    hechos: dict[str, dict] = {k: v for k, v in previo.items() if not solo or k not in solo}
    sha = hashlib.sha256(SISTEMA.encode()).hexdigest()[:12]

    def guardar():   # tras cada artículo: una corrida cortada se reanuda sin repetir
        salida.write_text(json.dumps({"fecha": date.today().isoformat(), "modelo": modelo, "prompt_sha": sha,
                                      "articulos": dict(sorted(hechos.items()))}, ensure_ascii=False, indent=1) + "\n")

    async def uno(aid: str, a: dict):
        async with sem:
            for intento in range(4):
                try:
                    r = await cli.generar(modelo, SISTEMA, usuario(a), {"type": "object"})
                    hechos[aid] = validar(json.loads(r.texto), a)
                    guardar()
                    return
                except Exception as e:  # noqa: BLE001 (se reintenta; no se imprime texto legal ni respuestas)
                    await asyncio.sleep(5 * (intento + 1))
                    err = type(e).__name__
            print("falló", aid, err, flush=True)

    pendientes = [k for k in arts if k not in hechos]
    print(f"{len(pendientes)} artículos por enriquecer de {len(arts)}", flush=True)
    await asyncio.gather(*(uno(k, arts[k]) for k in pendientes))
    guardar()
    print("escrito", salida, len(hechos), "artículos", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragmentos", required=True, help="JSON con los payloads vigentes de la colección")
    ap.add_argument("--modelo", default=MODELO)
    ap.add_argument("--salida", default=str(SALIDA))
    ap.add_argument("--solo", nargs="*", help="ids de artículo a regenerar")
    a = ap.parse_args(argv)
    asyncio.run(generar(json.loads(Path(a.fragmentos).read_text()), a.modelo, Path(a.salida), a.solo))


if __name__ == "__main__":
    main()
