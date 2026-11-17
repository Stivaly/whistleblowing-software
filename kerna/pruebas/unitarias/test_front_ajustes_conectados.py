"""Ajustes conectados en el panel: meta de respuesta, espera entre reintentos, alerta sin sugerencia y controles de Ajustes."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

from app import ajustes, cache, glosario, reintentos, vistas  # noqa: E402
from test_front_pendientes_reales import cliente, fila  # noqa: E402,F401
from test_front_reintentos import H  # noqa: E402
from test_front_vistas import EV, M  # noqa: E402


@pytest.fixture(autouse=True)
def _cache_limpia():
    cache.vaciar()
    yield
    cache.vaciar()


def guardado(**kw):
    cache.poner(("ajustes",), {"valores": {**ajustes.RECOMENDADO, **kw}, "guardado_en": "2026-11-17T10:00:00Z"})


def test_meta_respuesta_usa_lo_guardado_y_cae_al_defecto(monkeypatch):
    monkeypatch.setattr(ajustes, "cargar", lambda tabla=None: (_ for _ in ()).throw(RuntimeError("sin tabla")))
    assert ajustes.meta_respuesta_s() == 15
    guardado(maxresp=30)
    assert ajustes.meta_respuesta_s() == 30


def test_el_resumen_usa_la_meta_guardada():
    guardado(maxresp=30)
    v = vistas.resumen(M, EV, None, None, None, [], None, 7)
    k = {x["k"]: x for x in v["kpis"]}
    assert k["tiempo"]["metaT"] == "meta 30 s" and k["tiempo"]["meta"] == 30 and "Meta: 30 s" in k["tiempo"]["x"]
    assert k["tiempo"]["e"] == "warn"                                   # 41 s: entre la meta (30) y el doble (60)
    assert v["graficos"]["lat"]["meta"] == 30 and v["rapidez"]["meta"] == "30"
    guardado(maxresp=15)
    v = vistas.resumen(M, EV, None, None, None, [], None, 7)
    assert {x["k"]: x for x in v["kpis"]}["tiempo"]["e"] == "bad"


def test_los_ayuda_del_resumen_dicen_la_meta_guardada():
    guardado(maxresp=45)
    g = glosario.glosario()
    assert "45 s" in g["tiempo"]["q"] and "45 s" in g["latencia"]["q"]
    assert glosario.NOTAS_AJUSTE["compartir"] == "Quitar un equipo no le quita lo ya compartido."
    assert glosario.NOTAS_AJUSTE["alerta"] == "Más corto: se destacan antes los casos sin sugerencia."


def test_el_informe_formal_sigue_con_los_15_s():
    from app import informe
    guardado(maxresp=60)
    assert informe.META_P95_MS == 15000 and vistas.META_P95_S == 15


def test_horas_auto_sigue_la_espera_guardada(monkeypatch):
    monkeypatch.setattr(ajustes, "cargar", lambda tabla=None: (_ for _ in ()).throw(RuntimeError("sin tabla")))
    assert reintentos.horas_auto() == 24
    guardado(espera=6)
    assert reintentos.horas_auto() == 6


def test_el_proximo_reintento_estimado_usa_horas_auto():
    from datetime import datetime, timezone
    guardado(espera=12)
    ult = "2026-11-10T00:00:00Z"
    respuestas = iter([[{"motivo": "cadena_agotada", "casos": 2}], [{"evento": "conector_reintento", "eventos": 1, "ultimo": ult}]])
    ejecutar = lambda q, d: next(respuestas)  # noqa: E731
    r = reintentos.resumen(7, ejecutar=ejecutar, ahora=datetime(2026, 11, 10, 1, tzinfo=timezone.utc))
    assert r["proximo_auto"].startswith("2026-11-10T12:00:00")


def test_con_estado_real_entrega_la_alerta():
    base = fila()
    r = reintentos.con_estado_real(None, {**base, "sin_sugerencia_alerta": 3, "alerta_h": 6})
    assert r["alerta_n"] == 3 and r["alerta_h"] == 6
    r = reintentos.con_estado_real(None, base)
    assert r["alerta_n"] == 0 and r["alerta_h"] == 0
    r = reintentos.con_estado_real(None, {**base, "sin_sugerencia_alerta": "x", "alerta_h": None})
    assert r["alerta_n"] == 0 and r["alerta_h"] == 0


def test_el_panel_destaca_los_casos_sin_sugerencia_tras_la_alerta(cliente, monkeypatch):
    from datetime import datetime, timezone
    c, t = cliente
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(reintentos, "estado_conector", lambda tabla=None: fila(en_revision_manual=0, error=0, sin_sugerencia_alerta=2, alerta_h=6, actualizado_en=ahora))
    p = c.get("/panel", headers=H).text
    rei = p.split('id="rei"')[1].split("</section>")[0]
    assert "Más de 6 h sin sugerencia" in rei and 'cola-m s-bad' in rei and "Sin casos en espera" not in rei
    cache.vaciar()
    monkeypatch.setattr(reintentos, "estado_conector", lambda tabla=None: fila(en_revision_manual=0, error=0, sin_sugerencia_alerta=0, alerta_h=6, actualizado_en=ahora))
    rei = c.get("/panel", headers=H).text.split('id="rei"')[1].split("</section>")[0]
    assert "sin sugerencia" not in rei and "Sin casos en espera" in rei
    cache.vaciar()
    monkeypatch.setattr(reintentos, "estado_conector", lambda tabla=None: fila(sin_sugerencia_alerta=1, alerta_h=24, actualizado_en=ahora))
    rei = c.get("/panel", headers=H).text.split('id="rei"')[1].split("</section>")[0]
    assert "Más de 24 h sin sugerencia" in rei and "En revisión manual" in rei


def test_el_javascript_de_ajustes_escala_los_satelites_y_protege_el_ultimo_modelo():
    js = (Path(__file__).resolve().parents[2] / "front/app/estaticos/ajustes.js").read_text()
    assert "Math.round(v.candidatos * 20 / items.candidatos.max)" in js and "i < nc" in js
    assert "aria-disabled" in js and "filter((x) => x.on).length < 2" in js


def test_el_aviso_de_candidatos_usa_el_rango_nuevo(cliente):
    c, _ = cliente
    t = c.get("/panel/ajustes", headers=H).text
    assert '"max": 70' in t.replace("&#34;", '"') or '"max":70' in t.replace(" ", "").replace("&#34;", '"')


def test_el_desplegador_empaqueta_solo_el_esquema_de_ajustes():
    sh = (Path(__file__).resolve().parents[2] / "front/desplegar.sh").read_text()
    assert "ajustes_esquema.py" in sh and "kerna/comun" in sh and "kerna_comun" in sh
