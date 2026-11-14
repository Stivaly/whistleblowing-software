"""A11 un solo botón «Informe»; A12 «revisión manual» y «sin sugerencia» cuentan casos de Veridy (fila `conector`); A13 calidad = set desarrollo con la configuración vigente."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import evaluaciones, informe, reintentos, vistas  # noqa: E402
from test_front_informe import EVAL, FIN, INI, falso  # noqa: E402
from test_front_vistas import EV, M  # noqa: E402

PLANTILLAS = Path(__file__).resolve().parents[2] / "front" / "app" / "plantillas"
CONECTOR = {"actualizado_en": "2026-11-14T10:00:00Z", "casos": 116, "completado": 116, "en_revision_manual": 0, "error": 0, "nuevo": 0, "pendiente": 0}


def test_a11_informe_solo_en_el_menu_generar_informe():
    for nombre in ("panel.html", "negocio.html", "ajustes.html"):
        assert "/panel/informe" not in (PLANTILLAS / nombre).read_text(encoding="utf-8"), nombre
    assert "Generar informe" in (PLANTILLAS / "base_panel.html").read_text(encoding="utf-8")


def test_a12_el_conector_cuenta_casos_distintos_que_existen():
    r = reintentos.con_estado_real(None, {**CONECTOR, "en_revision_manual": 3, "completado": 113, "casos": 116})
    assert r["manual"] == 3 and r["con_sugerencia"] == 110 and r["sin_sugerencia"] == 6
    assert [x for x in r["manual_motivos"]] == [("En revisión manual", 3)]
    r0 = reintentos.con_estado_real(None, CONECTOR)
    assert (r0["manual"], r0["sin_sugerencia"], r0["manual_motivos"]) == (0, 0, [])


def test_a12_resumen_ignora_los_eventos_de_telemetria_si_hay_conector():
    m = {**M, "modos": {**M["modos"], "manual": 261}}
    v = vistas.resumen(m, EV, None, None, None, [], None, 7, conector=reintentos.con_estado_real(None, CONECTOR))
    assert next(x for x in v["modos"] if x["k"] == "manual")["n"] == 0
    assert v["sug_real"] and v["sug_pct"] == 100
    v2 = vistas.resumen(m, EV, None, None, None, [], None, 7)
    assert next(x for x in v2["modos"] if x["k"] == "manual")["n"] == 261 and not v2["sug_real"]


def test_a12_informe_cuenta_revision_manual_con_el_conector():
    inf = informe.construir(INI, FIN, ejecutar=falso, evaluacion=EVAL, conector=reintentos.con_estado_real(None, CONECTOR))
    kp = {k["etiqueta"]: k["valor"] for s in inf["secciones"] for k in s["kpis"]}
    assert kp["Revisión manual"] == 0 and kp["Casos en revisión manual"] == 0
    sin = informe.construir(INI, FIN, ejecutar=falso, evaluacion=EVAL)
    assert {k["etiqueta"]: k["valor"] for s in sin["secciones"] for k in s["kpis"]}["Casos en revisión manual"] == 2


def test_a12_consultas_historicas_cuentan_un_caso_por_su_ultimo_estado():
    kql = Path(__file__).resolve().parents[2] / "docs" / "observabilidad" / "consultas"
    for n in ("front_casos_por_dia", "informe_revision_manual", "front_pendientes_motivos", "solicitudes_por_modo", "disponibilidad_efectiva"):
        assert "arg_max(TimeGenerated, Properties) by id" in (kql / f"{n}.kql").read_text(encoding="utf-8"), n


def _fila(fecha, valor, coleccion="normativa_cl", particion="desarrollo", ambito="global"):
    return {"PartitionKey": "recall_retriever", "RowKey": f"{fecha}~{ambito}", "fecha": fecha, "commit": "c", "metrica": "recall5", "ambito": ambito, "valor": valor,
            "parametros": json.dumps({"particion": particion, "coleccion": coleccion, "configuracion": f"cfg {fecha}", "dataset_casos": 50, "campo_consulta": "texto_original"}),
            "detalle": json.dumps({"casos": 50, "casos_articulo": 42, "recall_ley": 0.9})}


FILAS = [_fila("2026-11-13T18:00:00+00:00", 0.55), _fila("2026-11-13T23:00:00+00:00", 0.643, coleccion="normativa_cl_x_e"),
         _fila("2026-11-14T01:00:00+00:00", 0.30, particion="prueba3"), _fila("2026-11-14T02:00:00+00:00", 0.20, particion="prueba2")]


def test_a13_sin_marca_toma_desarrollo_sobre_la_coleccion_desplegada():
    r = evaluaciones.construir(FILAS)["recall"]
    assert r["set"] == "desarrollo" and r["fecha"] == "2026-11-13T18:00:00+00:00"
    assert r["por_ley"][0]["recall5"] == 0.55


def test_a13_la_marca_vigente_elige_la_configuracion():
    marca = {"PartitionKey": "vigente", "RowKey": "desarrollo", "corrida": "2026-11-13T23:00:00+00:00"}
    r = evaluaciones.construir(FILAS + [marca])["recall"]
    assert r["fecha"] == "2026-11-13T23:00:00+00:00" and r["por_ley"][0]["recall5"] == 0.643


def test_a13_el_panel_nombra_el_set():
    v = vistas.resumen(M, EV, None, None, None, [], None, 7)
    p = vistas.presentacion_resumen(v, None, 7)
    assert next(k for k in p["kb"] if k["k"] == "calidad")["sub"] == "Set desarrollo"


def test_a13_el_informe_nombra_el_set_en_la_banda():
    inf = informe.construir(INI, FIN, ejecutar=falso, evaluacion=EVAL)
    v = vistas.informe_v2(inf)
    assert next(k for k in v["kb"] if k["k"] == "calidad")["sub"] == "Set desarrollo"
