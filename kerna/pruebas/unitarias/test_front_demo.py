"""Demo del panel: ruta protegida, anonimizador (resultado, resumen, colores), sin guardar ni registrar el texto, y empaquetado."""
import logging
import os
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"

from fastapi.testclient import TestClient  # noqa: E402

from app import demo_anon, principal, seguridad  # noqa: E402

H = {"x-clave": "clave-de-prueba"}
RELATO = "Me llamo Marcela Fuentes Araya, RUT 14.567.890-1, escríbeme a marcela.fuentes@gmail.com o al +56 9 8123 4567."


@pytest.fixture
def c():
    return TestClient(principal.app, base_url="https://t", follow_redirects=False)


def _csrf():
    return seguridad.token_csrf({})  # con la clave por cabecera no hay cookie: el token se liga a «sin-cookie»


def _post(c, texto=RELATO, **extra):
    return c.post("/panel/demo/anonimizar", data={"csrf": _csrf(), "texto": texto, **extra}, headers={**H, "Accept": "application/json"})


def test_demo_exige_sesion(c):
    r = c.get("/panel/demo")
    assert r.status_code == 303 and r.headers["location"] == "/acceso"
    r = c.post("/panel/demo/anonimizar", data={"csrf": _csrf(), "texto": RELATO})
    assert r.status_code == 303 and r.headers["location"] == "/acceso"
    r = c.post("/panel/demo/anonimizar", data={"csrf": _csrf(), "texto": RELATO}, headers={"Accept": "application/json"})
    assert r.status_code == 401


def test_pagina_demo_con_menu_y_pestana_anonimizador(c):
    r = c.get("/panel/demo", headers=H)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    t = r.text
    assert t.count('href="/panel/demo"') == 2 and 'aria-current="page"' in t       # menú de escritorio y barra móvil
    assert "Anonimizador" in t and "demo.js" in t and '<textarea id="dmo-texto"' in t
    assert len(re.findall(r'name="relato" value="', t)) == len(demo_anon.RELATOS) >= 3
    assert "ejemplo" not in t.lower() and "ficticio" not in t.lower()
    assert 'href="#n-demo"' in t and 'id="n-demo"' in t


def test_anonimiza_y_resume_por_tipo(c):
    r = _post(c)
    assert r.status_code == 200 and r.json()["estado"] == "ok"
    h = r.json()["html"]
    assert "[PERSONA_1]" in h and "[RUT_1]" in h and "[CORREO_1]" in h and "[TELEFONO_1]" in h
    assert "4 datos personales ocultados" in h
    assert h.count('class="an-m"') == 8                                        # 4 en el original y 4 en el anonimizado
    assert 'data-c="violeta"' in h and 'data-c="azul"' in h
    assert "Texto original" in h and "Texto anonimizado" in h


def test_analizar_reconstruye_los_dos_textos_y_los_colores_son_fijos():
    for _, _, x in demo_anon.RELATOS:
        a = demo_anon.analizar(x)
        assert "".join(s[0] for s in a["original_seg"]) == a["texto"]
        assert "".join(s[0] for s in a["anonimizado_seg"]) == a["anonimizado"]
        assert a["total_entidades"] >= 4 and 0 < a["porcentaje_oculto"] < 100
        assert all(m[0] == a["anonimizado"][a["anonimizado"].index(m[0]):][:len(m[0])] for m in a["anonimizado_seg"] if m[1])
    colores = [v[2] for v in demo_anon.TIPOS.values()]
    assert len(set(colores)) == len(colores) == 8
    tipos_del_anonimizador = __import__("kerna_comun.anonimizador", fromlist=["TIPOS"]).TIPOS
    assert set(demo_anon.TIPOS) == set(tipos_del_anonimizador)


def test_sin_datos_personales_lo_dice(c):
    h = _post(c, "La puerta de emergencia de la bodega estaba bloqueada con cajas desde el lunes.").json()["html"]
    assert "No se encontraron datos personales" in h and "an-m" not in h


def test_limite_de_largo_y_vacio(c):
    h = _post(c, "Hola, soy Marcela Fuentes Araya. " * 400).json()["html"]
    assert f"primeros {demo_anon.MAX_CARACTERES} caracteres" in h
    assert demo_anon.analizar("x" * 20000)["largo"] == demo_anon.MAX_CARACTERES
    assert _post(c, "   ").status_code == 400


def test_sin_javascript_el_formulario_devuelve_la_pagina_y_los_precargados_funcionan(c):
    r = c.post("/panel/demo/anonimizar", data={"csrf": _csrf(), "texto": RELATO}, headers=H)
    assert r.status_code == 200 and "[RUT_1]" in r.text and "<textarea" in r.text
    k = demo_anon.RELATOS[0][0]
    r = c.post("/panel/demo/anonimizar", data={"csrf": _csrf(), "texto": "", "relato": k}, headers=H)
    assert r.status_code == 200 and "[PERSONA_1]" in r.text and "Marcela Fuentes" in r.text
    assert c.post("/panel/demo/anonimizar", data={"csrf": _csrf(), "texto": ""}, headers=H).status_code == 400


def test_csrf_y_origen(c):
    assert c.post("/panel/demo/anonimizar", data={"csrf": "malo", "texto": RELATO}, headers={**H, "Accept": "application/json"}).json()["estado"] == "token"
    r = c.post("/panel/demo/anonimizar", data={"csrf": _csrf(), "texto": RELATO}, headers={**H, "Accept": "application/json", "Origin": "https://otro.example"})
    assert r.status_code == 403 and r.json()["estado"] == "origen"


def test_no_guarda_ni_registra_el_texto(c, caplog, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    secreto = "Hernán Castillo Vera"
    with caplog.at_level(logging.DEBUG):
        r = _post(c, f"El cliente, don {secreto}, RUT 7.654.321-K, reclamó.")
    assert r.status_code == 200 and "[PERSONA_1]" in r.json()["html"]
    salida = capsys.readouterr()
    assert secreto not in caplog.text and secreto not in salida.out + salida.err
    assert list(tmp_path.iterdir()) == []
    fuente = (RAIZ / "front/app/demo_anon.py").read_text() + (RAIZ / "front/app/principal.py").read_text().split("# ---- Demo:")[1]
    assert not re.search(r"\b(print|logging|logger|open\(|write\()", fuente)


def test_el_desplegador_empaqueta_el_anonimizador():
    sh = (RAIZ / "front/desplegar.sh").read_text()
    linea = next(l for l in sh.splitlines() if l.lstrip().startswith("mkdir -p") and "kerna_comun" in l)
    assert "$COMUN/anonimizador.py" in linea and "$TMP/kerna_comun/" in linea
    # el anonimizador solo usa la biblioteca estándar: el front desplegado (sin el resto de kerna_comun) puede importarlo
    fuente = (RAIZ / "comun/kerna_comun/anonimizador.py").read_text()
    assert set(re.findall(r"^(?:from|import) (\w+)", fuente, re.M)) <= {"__future__", "re", "unicodedata", "dataclasses"}


def test_contrato_con_demo_denuncias(c, monkeypatch):
    """Si existe `demo_denuncias`, su contexto llega a la plantilla como `den` y la pestaña «Denuncias» aparece; si no, no se muestra."""
    assert 'data-pestana="denuncias"' not in c.get("/panel/demo", headers=H).text or principal.demo_denuncias is not None
    falso = type("M", (), {"contexto": staticmethod(lambda: {"casos": 3})})
    monkeypatch.setattr(principal, "demo_denuncias", falso)
    t = c.get("/panel/demo?pestana=denuncias", headers=H).text
    assert 'data-pestana="denuncias"' in t and 'id="dmo-denuncias" data-panel="denuncias" aria-label' in t
    monkeypatch.setattr(principal, "demo_denuncias", type("M", (), {"contexto": staticmethod(lambda: 1 / 0)}))
    assert c.get("/panel/demo", headers=H).status_code == 200                  # un fallo de la otra parte no rompe el anonimizador
