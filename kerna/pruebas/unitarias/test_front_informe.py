"""Pruebas del informe de gestión (HTML, XLSX, CSV, PDF) con Log Analytics y evaluación simulados."""
import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import exportar, informe, principal, seguridad  # noqa: E402

INI, FIN = datetime(2026, 10, 13, tzinfo=timezone.utc), datetime(2026, 11, 12, tzinfo=timezone.utc)
EVAL = {"generado": "2026-11-12T00:00:00+00:00", "corpus_articulos": 144,
        "recall": {"fecha": "2026-11-12T02:37:57+00:00", "commit": "abc", "configuracion": "prueba", "meta": 0.8, "dataset_casos": 113, "fuente": "registro.jsonl",
                   "por_ley": [{"ley": "Global", "casos": 91, "casos_articulo": 61, "recall_ley": 0.93, "recall5": 0.377, "ic95_inf": 0.26, "ic95_sup": 0.49},
                               {"ley": "21.643", "casos": 29, "casos_articulo": 28, "recall_ley": 0.93, "recall5": 0.85, "ic95_inf": 0.7, "ic95_sup": 0.9}]},
        "serie": [{"fecha": "2026-11-11 03:24", "configuracion": "x", "recall5": 0.5}],
        "anonimizador": {"fecha": "2026-11-11", "casos": 113, "fuente": "a.json", "tipos": [{"tipo": "RUT", "casos_con_dato": 1, "casos_detectados": 1, "recall_por_caso": 1.0}],
                         "apariciones": [{"tipo": "EDAD", "total": 36, "ocultas": 0}]},
        "pruebas": {"fecha": "2026-11-11", "commit": "abc", "fuente": "p.json", "capas": {"unitarias": {"total": 10, "pasadas": 10, "fallidas": 0, "omitidas": 0}}},
        "evaluador": {"cadena": "gpt-5-nano", "costo_usd": 0.128, "latencia_llamada_ms": {"mediana": 13742.0, "p95": 27540.0}},
        "precios_embeddings": {"voyage-4-large": None, "voyage-law-2": 0.12}}


def falso(texto, ini, fin):
    if "conector_reintento" in texto:
        return [{"evento": "conector_reintento", "intento": "1", "motivo": "cadena_agotada", "eventos": 4, "casos": 3},
                {"evento": "conector_reproceso", "intento": "1", "motivo": "", "eventos": 2, "casos": 2}]
    if "by modelo" in texto:
        return [{"modelo": "gpt-5-nano", "solicitudes": 8, "tokens_entrada_total": 160000, "tokens_salida_total": 24000, "tokens_entrada_prom": 20000},
                {"modelo": "gpt-5-mini", "solicitudes": 1, "tokens_entrada_total": 10000, "tokens_salida_total": 2000, "tokens_entrada_prom": 10000},
                {"modelo": "gemini-x", "solicitudes": 1, "tokens_entrada_total": 10000, "tokens_salida_total": 1000, "tokens_entrada_prom": 10000}]
    if "articulo_sugerido" in texto:
        return [{"norma": "Ley 21643", "articulos": 5}]
    if "front_valoraciones" in texto or "clasificacion_auditor" in texto:
        return [{"valoracion": "util", "total": 4}, {"valoracion": "no_util", "total": 1}]
    if "etapa" in texto:
        return [{"etapa": "generacion", "solicitudes": 9, "p50_ms": 3000, "p95_ms": 9000, "max_ms": 12000}]
    if "percentile" in texto:
        return [{"dia": "2026-11-10T00:00:00Z", "solicitudes": 3, "p50_ms": 4000.4, "p95_ms": 9000.2}]
    if "tokens_entrada_total" in texto:
        return [{"modo": "oficial", "solicitudes": 8, "tokens_entrada_total": 160000, "tokens_salida_total": 24000, "tokens_entrada_prom": 20000, "tokens_salida_prom": 3000}]
    if "validas" in texto:
        return [{"validas": 9, "con_sugerencia": 7}]
    if "nivel_fallido" in texto:
        return [{"evento": "nivel_fallido", "proveedor": "generacion", "modelo": "m", "codigo": "429", "eventos": 3}]
    if "revision_manual" in texto:
        return [{"motivo": "cadena_agotada", "casos": 2}]
    if "recuperacion" in texto:
        return [{"modo": "oficial", "recuperacion": "nube", "solicitudes": 6}, {"modo": "manual", "recuperacion": "nube", "solicitudes": 2}]
    return [{"dia": "2026-11-10T00:00:00Z", "casos": 9, "con_sugerencia": 7}]


@pytest.fixture(scope="module")
def inf():
    return informe.construir(INI, FIN, ejecutar=falso, evaluacion=EVAL)


def test_secciones_y_sin_proximos_pasos(inf):
    ids = [s["id"] for s in inf["secciones"]]
    assert ids == ["resumen", "calidad", "desempeno", "costo", "rentabilidad", "cobertura", "incidentes"]


def test_costo_real_por_modelo_con_equivalencia(inf):
    c = next(s for s in inf["secciones"] if s["id"] == "costo")
    filas = {f[0]: f for f in c["tablas"][0]["filas"]}
    haiku = 170000 * .10 / 1e6 + 25000 * .50 / 1e6
    sonnet = 10000 * 2 / 1e6 + 2000 * 10 / 1e6
    assert filas["Claude Haiku 5.5"][5] == pytest.approx(haiku, abs=1e-4) and filas["Claude Sonnet 5.5"][5] == pytest.approx(sonnet, abs=1e-4)
    assert "Claude Opus 5.5" not in filas
    k = {x["etiqueta"]: x["valor"] for x in c["kpis"]}
    assert k["Costo del período"] == pytest.approx(haiku + sonnet, abs=1e-3)
    assert k["Costo por denuncia"] == pytest.approx((haiku + sonnet) / 10, abs=1e-5)
    assert k["Costo de IA mensual proyectado, 1.000 denuncias"] == pytest.approx((haiku + sonnet) / 10 * 1000, abs=0.01)
    texto = str(c).lower()
    assert "estimaci" not in texto and "escenario" not in texto and "tokenizador" not in texto and "opus" not in texto
    assert any("gemini-x" in n and "Haiku" in n for n in c["notas"])


def test_dato_faltante_se_declara():
    def roto(t, i, f):
        raise RuntimeError("x")
    r = informe.construir(INI, FIN, ejecutar=roto, evaluacion=None)
    assert any("Sin datos" in n for s in r["secciones"] for n in s["notas"])


def test_csv(inf):
    b = exportar.a_csv(inf)
    assert b.startswith(b"\xef\xbb\xbf") and "seccion;metrica;valor;unidad;fuente;fecha_corte" in b.decode("utf-8-sig")
    assert "Casos procesados;9" in b.decode("utf-8-sig")


def test_xlsx(inf):
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(exportar.a_xlsx(inf)))
    assert wb.sheetnames[0] == "Resumen" and "Costo y consumo" in wb.sheetnames and "Próximos pasos" not in wb.sheetnames
    assert len(wb["Resumen"]._images) == 1


def test_pdf(inf):
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(exportar.a_pdf(inf)))
    texto = " ".join(p.extract_text() for p in r.pages)
    assert len(r.pages) >= 4 and "Informe de gestión" in texto and "Claude Haiku 5.5" in texto


def test_rutas(monkeypatch):
    monkeypatch.setattr(informe, "_filas_rango", falso)
    monkeypatch.setattr(informe.evaluaciones, "cargar", lambda *a, **k: EVAL)
    c = TestClient(principal.app, follow_redirects=False)
    assert c.get("/panel/informe").status_code == 303 and c.get("/panel/informe/descargar.pdf").status_code == 303
    c.cookies.set(seguridad.COOKIE, seguridad.emitir_cookie())
    assert c.get("/panel/informe?dias=7").status_code == 200
    assert c.get("/panel/informe?desde=2026-11-01&hasta=2026-11-10").status_code == 200
    for ext, firma in (("xlsx", b"PK"), ("csv", b"\xef\xbb\xbf"), ("pdf", b"%PDF")):
        r = c.get(f"/panel/informe/descargar.{ext}?dias=30")
        assert r.status_code == 200 and r.content.startswith(firma)


def test_reintentos_y_consumo_por_modelo_desde_log_analytics(inf):
    des = next(x for x in inf["secciones"] if x["id"] == "desempeno")
    assert next(k for k in des["kpis"] if k["etiqueta"].startswith("Reintentos"))["valor"] == 4
    assert any(t["id"] == "reintentos" and t["filas"][0][:2] == ["1", "cadena_agotada"] for t in des["tablas"])
    costo = next(x for x in inf["secciones"] if x["id"] == "costo")
    assert any(t["id"] == "tokens_modelo" and t["filas"][0][0] == "gpt-5-nano" for t in costo["tablas"])


def test_tabla_evaluaciones_caida_se_declara_sin_datos(monkeypatch):
    def roto():
        raise RuntimeError("sin rol")
    monkeypatch.setattr(informe.evaluaciones, "cargar", roto)
    r = informe.construir(INI, FIN, ejecutar=falso)
    cal = next(x for x in r["secciones"] if x["id"] == "calidad")
    assert any("tabla `evaluaciones` no respondió" in n for n in cal["notas"])


def test_rentabilidad_con_costos_del_capitulo_en_todos_los_formatos():
    from app import negocio
    cl = [{"PartitionKey": "p", "nombre": "P", "plan_tipo": "pro", "plan_denuncias_mes": 300, "estado": "activo", "origen_veridy": True}]
    n = negocio.construir(cl, [], hoy=FIN.date(), dias=30)
    r = informe.construir(INI, FIN, ejecutar=falso, evaluacion=EVAL, negocio=n)
    rent = next(x for x in r["secciones"] if x["id"] == "rentabilidad")
    k = {x["etiqueta"].split(" (")[0]: x for x in rent["kpis"]}
    assert k["Costos fijos del período"]["unidad"] == "UF" and k["Costos fijos del período"]["valor"] == n["totales"]["costos_fijos"] > 0
    assert k["Valor actual neto de la proyección"]["valor"] == n["proyeccion"]["van"]
    assert len(next(t for t in rent["tablas"] if t["id"] == "rent_proyeccion")["filas"]) == 5
    assert exportar.a_xlsx(r).startswith(b"PK") and exportar.a_pdf(r).startswith(b"%PDF") and b"Rentabilidad" in exportar.a_csv(r)
    vacio = next(x for x in informe.construir(INI, FIN, ejecutar=falso, evaluacion=EVAL)["secciones"] if x["id"] == "rentabilidad")
    assert vacio["kpis"] == [] and vacio["notas"]


def test_ley_19628_se_nombra_con_su_reforma_21719():
    assert informe.nombre_ley("19.628-21.719") == "Ley 19.628 (datos personales), reformada por la Ley 21.719"
    ev = {**EVAL, "recall": {**EVAL["recall"], "por_ley": EVAL["recall"]["por_ley"] + [
        {"ley": "19.628-21.719", "casos": 5, "casos_articulo": 4, "recall_ley": 0.9, "recall5": 0.5, "ic95_inf": None, "ic95_sup": None}]}}
    cal = next(x for x in informe.construir(INI, FIN, ejecutar=falso, evaluacion=ev)["secciones"] if x["id"] == "calidad")
    t = next(t for t in cal["tablas"] if t["id"] == "recall_ley")
    assert any(f[0] == "Ley 19.628 (datos personales), reformada por la Ley 21.719" for f in t["filas"])
    assert any(i[0] == informe.NOMBRE_19628 for g in cal["graficos"] for i in g["items"])
