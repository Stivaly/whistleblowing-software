"""Demo del panel, sección «Denuncias»: casos con su respuesta esperada, conexión con el núcleo (simulado por HTTP), comparación y
garantía de que el texto no se guarda ni se registra."""
import json
import logging
import os
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"

from fastapi.testclient import TestClient  # noqa: E402

from app import demo_denuncias as dd, principal, seguridad  # noqa: E402
import sesion_prueba  # noqa: E402
from app.demo_denuncias_casos import CASOS, POR_ID  # noqa: E402

from sesion_prueba import H  # noqa: E402  (cookie de la sesión de Dirección)
HJ = {**H, "Accept": "application/json"}
CORPUS = RAIZ / "evaluacion" / "datos" / "corpus_texto_20261115.md"
CASO = CASOS[0]


def _csrf():
    return sesion_prueba.csrf()


# ---- núcleo simulado por HTTP (OAuth client credentials, POST /v1/casos, GET /v1/casos/{ref}/sugerencia) ------------------------------

class NucleoFalso:
    def __init__(self, respuesta=None):
        self.respuesta = respuesta or {"estado": "completada", "articulos": []}
        self.pendientes = 0           # cuántas consultas responden «pendiente» antes de la respuesta
        self.casos, self.tokens, self.consultas = [], [], 0
        self.rechazar_credenciales = False
        falso = self

        class Manejador(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _responder(self, codigo, cuerpo):
                datos = json.dumps(cuerpo).encode()
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                cuerpo = self.rfile.read(n).decode()
                if self.path == "/oauth/token":
                    f = {k: v[0] for k, v in urllib.parse.parse_qs(cuerpo).items()}
                    falso.tokens.append(f)
                    if falso.rechazar_credenciales or f.get("grant_type") != "client_credentials" or f.get("client_secret") != "secreto-demo":
                        return self._responder(401, {"detail": "credenciales inválidas"})
                    return self._responder(200, {"access_token": "tok-demo", "token_type": "bearer", "expires_in": 600})
                if self.headers.get("Authorization") != "Bearer tok-demo":
                    return self._responder(401, {"detail": "no autorizado"})
                if self.path == "/v1/casos":
                    falso.casos.append(json.loads(cuerpo))
                    return self._responder(202, {"id_solicitud": "x", "estado": "pendiente"})
                self._responder(404, {})

            def do_GET(self):
                if self.headers.get("Authorization") != "Bearer tok-demo":
                    return self._responder(401, {})
                falso.consultas += 1
                if falso.consultas <= falso.pendientes:
                    return self._responder(200, {"id_solicitud": "x", "estado": "pendiente"})
                self._responder(200, {"id_solicitud": "x", **falso.respuesta})

        self.servidor = HTTPServer(("127.0.0.1", 0), Manejador)
        self.url = f"http://127.0.0.1:{self.servidor.server_port}"
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


def art(id_articulo, norma="Ley 21.643", articulo="1", dictamen=None, confianza=0.7):
    a = {"id_sugerencia": "s", "id_articulo": id_articulo, "norma": norma, "articulo": articulo,
         "explicacion": "Los hechos se relacionan con este artículo.", "cita": "texto citado", "enlace_fuente": "", "confianza": confianza}
    if dictamen:
        a.update(revision_juridica="revisado", dictamen=dictamen)
    return a


@pytest.fixture
def web(monkeypatch):
    nucleo = NucleoFalso()
    monkeypatch.setenv("KERNA_NUCLEO_URL", nucleo.url)
    monkeypatch.setenv("DEMO_CLIENT_ID", "demo-panel-dev")
    monkeypatch.setenv("DEMO_CLIENT_SECRET", "secreto-demo")
    monkeypatch.setattr(dd, "_token", {"valor": "", "vence": 0.0})
    monkeypatch.setattr(dd, "_envios", [])
    monkeypatch.setattr(dd, "_refs", {})
    c = TestClient(principal.app, base_url="https://t", follow_redirects=False)
    c.nucleo = nucleo
    yield c
    nucleo.cerrar()


def enviar(web, texto=None, caso=None, **extra):
    caso = CASO["id"] if caso is None else caso
    texto = POR_ID[caso]["texto"] if texto is None and caso in POR_ID else (texto or "")
    return web.post("/panel/demo/denuncia", headers=HJ, data={"csrf": _csrf(), "texto": texto, "caso": caso, **extra})


# ---- los casos ----------------------------------------------------------------------------------------------------------------

def test_hay_diez_casos_y_al_menos_dos_quedan_sin_sugerencia():
    assert len(CASOS) == 10 and len({c["id"] for c in CASOS}) == 10
    fuera = [c for c in CASOS if c["tipo"] == "fuera"]
    assert len(fuera) >= 2 and all(c["fuera"] and not c["articulos"] for c in fuera)
    assert {c["tipo"] for c in CASOS} == {"karin", "datos", "penal", "fuera"}
    for c in CASOS:
        if c["tipo"] != "fuera":
            assert len(c["articulos"]) >= 3 and all(dd.tipo_ley(i) == c["tipo"] for i, _ in c["articulos"]), c["id"]


def test_los_relatos_son_completos_y_traen_datos_personales_para_el_anonimizador():
    from kerna_comun import anonimizador
    for c in CASOS:
        t = c["texto"]
        assert dd.MIN_CARACTERES < len(t) <= dd.MAX_CARACTERES, c["id"]
        assert not re.search(r"ejemplo|ficticio", t, re.I), c["id"]
        r = anonimizador.anonimizar(t)
        assert r.conteos.get("PERSONA") and (c["tipo"] == "fuera" or r.conteos.get("TELEFONO") or r.conteos.get("CORREO")), c["id"]  # los «fuera» van tal como están en el banco


def test_las_denuncias_fuera_del_corpus_no_tratan_las_leyes_del_corpus():
    for c in CASOS:
        if c["tipo"] == "fuera":
            assert not re.search(r"acoso|karin|datos personales|20\.393|persona jur", c["texto"], re.I), c["id"]


@pytest.mark.skipif(not CORPUS.exists(), reason="el corpus vigente está fuera de git")
def test_los_articulos_esperados_existen_en_el_corpus_vigente():
    corpus = set(re.findall(r"^## (\S+) — ", CORPUS.read_text(), re.M))
    faltan = [i for c in CASOS for i, _ in c["articulos"] if i not in corpus]
    assert not faltan, faltan


def test_ley_de_un_articulo():
    assert dd.tipo_ley("207436-karin-art-211-a") == "karin" and dd.tipo_ley("1200096-art-6") == "karin"
    assert dd.tipo_ley("141599-2026-12-01-art-16") == "datos" and dd.tipo_ley("1209272-art-t-sexto") == "datos"
    assert dd.tipo_ley("1008668-art-4") == "penal" and dd.tipo_ley("zzz", "Ley 19.628") == "datos" and dd.tipo_ley("zzz", "Ley 19.496") is None


# ---- comparación ---------------------------------------------------------------------------------------------------------------------

def _vista(articulos, caso=CASO["id"], estado="completada", **resto):
    return dd.vista_resultado({"estado": estado, "articulos": articulos, **resto}, POR_ID.get(caso))


def test_coincide_si_al_menos_un_articulo_esperado_esta_sugerido():
    v = _vista([art("207436-karin-art-211-c-p2"), art("141599-2026-12-01-art-16")])
    assert v["comparacion"] == "coincide" and [a["coincide"] for a in v["articulos"]] == [True, False] and v["esperado"]["articulos"][0]["etiqueta"]


def test_difiere_con_el_motivo():
    assert _vista([art("207436-karin-art-211-d")])["detalle"] == "misma_ley"
    assert _vista([art("141599-2026-12-01-art-16")])["detalle"] == "otra_ley"
    v = _vista([], estado="revision_manual", motivo_revision="validacion_fallida")
    assert v["estado"] == "sin_sugerencia" and v["comparacion"] == "difiere" and v["detalle"] == "sin_sugerencia" and v["motivo"] == "validacion_fallida"


def test_los_vetados_no_cuentan_como_sugerencia():
    v = _vista([art("207436-karin-art-211-a", dictamen="veta"), art("207436-karin-art-211-c", dictamen="condiciona")])
    assert v["vetados"] == 1 and [a["id"] for a in v["articulos"]] == ["207436-karin-art-211-c"] and v["articulos"][0]["veredicto"] == "condiciona"
    assert _vista([art("207436-karin-art-211-a", dictamen="veta")])["estado"] == "sin_sugerencia"


def test_fuera_del_corpus_coincide_sin_sugerencia_y_difiere_si_sugiere():
    ids = [c["id"] for c in CASOS if c["tipo"] == "fuera"]
    sin = _vista([], caso=ids[0], estado="revision_manual", motivo_revision="sin_normativa_aplicable")
    assert sin["comparacion"] == "coincide" and sin["esperado"]["tipo"] == "fuera" and sin["esperado"]["fuera"]
    con = _vista([art("207436-karin-art-2")], caso=ids[0])
    assert con["comparacion"] == "difiere" and con["detalle"] == "con_sugerencia"


def test_denuncia_propia_no_se_compara():
    v = _vista([art("207436-karin-art-2")], caso="")
    assert v["comparacion"] is None and v["esperado"] is None and v["estado"] == "listo"
    assert dd.vista_resultado({"estado": "pendiente"}, None) == {"estado": "procesando"}


# ---- rutas -----------------------------------------------------------------------------------------------------------------------------

def test_las_rutas_exigen_sesion_origen_y_token(web):
    d = {"csrf": _csrf(), "texto": CASO["texto"], "caso": CASO["id"]}
    assert web.post("/panel/demo/denuncia", headers={"Accept": "application/json"}, data=d).status_code == 401
    assert web.get("/panel/demo/denuncia/" + "0" * 8 + "-0000-0000-0000-" + "0" * 12).status_code == 401
    assert web.post("/panel/demo/denuncia", headers={**HJ, "Origin": "https://otro.example"}, data=d).json()["estado"] == "origen"
    assert web.post("/panel/demo/denuncia", headers=HJ, data={**d, "csrf": "mal"}).json()["estado"] == "token"
    assert web.nucleo.casos == []


def test_texto_corto_o_largo(web):
    assert enviar(web, texto="hola", caso="").json()["estado"] == "corto"
    assert enviar(web, texto="x" * (dd.MAX_CARACTERES + 1), caso="").json()["estado"] == "largo"
    assert web.nucleo.casos == []


def test_envia_al_nucleo_con_la_cuenta_de_demo_y_sigue_hasta_el_resultado(web):
    web.nucleo.pendientes = 1
    web.nucleo.respuesta = {"estado": "completada", "modo": "oficial", "motivo_revision": None,
                            "articulos": [art("207436-karin-art-211-a", "Código del Trabajo", "211 A")]}
    r = enviar(web)
    assert r.status_code == 200 and r.json()["estado"] == "ok"
    ref = r.json()["ref"]
    (tok,), (caso,) = web.nucleo.tokens, web.nucleo.casos
    assert tok == {"grant_type": "client_credentials", "client_id": "demo-panel-dev", "client_secret": "secreto-demo"}
    assert caso["ref_opaca"] == ref and caso["id_empresa"] == dd.ID_EMPRESA and caso["texto"] == CASO["texto"].strip()
    assert web.get(f"/panel/demo/denuncia/{ref}", headers=HJ).json() == {"estado": "procesando"}
    v = web.get(f"/panel/demo/denuncia/{ref}", headers=HJ).json()
    assert v["estado"] == "listo" and v["comparacion"] == "coincide" and v["articulos"][0]["ley"] == "karin" and v["articulos"][0]["coincide"]
    assert len(web.nucleo.tokens) == 1          # el token se reutiliza


def test_texto_modificado_deja_de_tener_respuesta_esperada(web):
    ref = enviar(web, texto=CASO["texto"] + " Además me insultó por teléfono.").json()["ref"]
    assert web.get(f"/panel/demo/denuncia/{ref}", headers=HJ).json()["esperado"] is None
    assert web.get("/panel/demo/denuncia/no-es-un-uuid", headers=HJ).status_code == 404
    assert web.get("/panel/demo/denuncia/" + "1" * 8 + "-1111-4111-8111-" + "1" * 12, headers=HJ).status_code == 404


def test_sin_nucleo_muestra_lo_esperado_guardado_y_no_un_error(web):
    web.nucleo.cerrar()
    r = enviar(web)
    d = r.json()
    assert r.status_code == 200 and d["estado"] == "sin_nucleo" and d["motivo"] == "no_responde"
    assert d["esperado"]["articulos"] and d["nucleo"] is False
    assert enviar(web, caso="", texto="x" * 80).json()["esperado"] is None


def test_sin_configurar_credenciales_o_url(web, monkeypatch):
    monkeypatch.setenv("DEMO_CLIENT_SECRET", "@Microsoft.KeyVault(SecretUri=https://kv/secrets/x/)")
    d = enviar(web).json()
    assert d["estado"] == "sin_nucleo" and d["motivo"] == "no_configurado" and d["esperado"]["articulos"] and not web.nucleo.tokens
    assert dd.contexto()["configurado"] is False
    monkeypatch.setenv("DEMO_CLIENT_SECRET", "secreto-demo")
    monkeypatch.delenv("KERNA_NUCLEO_URL")
    assert enviar(web).json()["motivo"] == "no_configurado"


def test_credenciales_rechazadas(web):
    web.nucleo.rechazar_credenciales = True
    d = enviar(web).json()
    assert d["estado"] == "sin_nucleo" and d["motivo"] == "credenciales" and d["esperado"]["articulos"]


def test_si_el_nucleo_deja_de_responder_a_mitad_el_seguimiento_muestra_lo_esperado(web):
    ref = enviar(web).json()["ref"]
    web.nucleo.cerrar()
    d = web.get(f"/panel/demo/denuncia/{ref}", headers=HJ).json()
    assert d["estado"] == "sin_nucleo" and d["esperado"]["articulos"]


def test_limite_de_uso(web):
    for _ in range(dd.TOPE_10_MIN):
        assert enviar(web).json()["estado"] == "ok"
    r = enviar(web)
    assert r.status_code == 429 and r.json()["estado"] == "limite"


# ---- el texto no se guarda ni se registra ---------------------------------------------------------------------------------------------------

def test_el_texto_no_se_guarda_ni_va_a_los_registros(web, caplog):
    caplog.set_level(logging.DEBUG)
    secreto = "Rodrigo Valenzuela Soto"
    assert secreto in CASO["texto"]
    ref = enviar(web).json()["ref"]
    web.get(f"/panel/demo/denuncia/{ref}", headers=HJ)
    assert secreto not in caplog.text and CASO["texto"][:60] not in caplog.text
    assert secreto not in repr(dd._refs) and secreto not in repr(dd._token) and secreto not in repr(dd._envios)
    fuente = (Path(dd.__file__).read_text() + (RAIZ / "front/app/estaticos/demo_den.js").read_text())
    assert not re.search(r"logging|logger|print\(|localStorage|sessionStorage|history\.(push|replace)State", fuente)


# ---- página, estáticos y diseño ----------------------------------------------------------------------------------------------------------------

def test_la_pestana_denuncias_muestra_casos_leyes_y_etiquetas(web):
    r = web.get("/panel/demo?pestana=denuncias", headers=H)
    t = r.text
    assert r.status_code == 200 and 'id="dmo-denuncias"' in t and "data-den " in t
    assert len(re.findall(r'class="den-caso"', t)) == 10 and "Escribir otra denuncia" in t
    assert t.count("Fuera del corpus") >= 2 and "Texto de la denuncia" in t and "Analizar denuncia" in t
    for ley in ("21.643", "19.628 y 21.719", "20.393"):
        assert ley in t
    assert 'data-l="karin"' in t and 'data-l="datos"' in t and 'data-l="penal"' in t and 'href="#m-sin-normativa"' in t
    assert t.count('class="den-q"') >= 3 and "demo_den.js" in t and "demo_den.css" in t
    assert not re.search(r"ejemplo|ficticio", t, re.I)
    assert f'data-csrf="{_csrf()}"' in t


def test_los_datos_de_la_pagina_son_json_valido_y_no_cierran_el_script(web):
    t = web.get("/panel/demo?pestana=denuncias", headers=H).text
    bloque = re.search(r'<script type="application/json" id="den-datos">(.*?)</script>', t, re.S).group(1)
    datos = json.loads(bloque)
    assert len(datos["casos"]) == 10 and datos["casos"][CASO["id"]]["texto"] == CASO["texto"] and datos["casos"][CASO["id"]]["esperado"]
    assert "<" not in bloque and datos["min"] == dd.MIN_CARACTERES
    fuera = [v for v in datos["casos"].values() if v["tipo"] == "fuera"]
    assert len(fuera) >= 2 and all(v["esperado"] == [] and v["fuera"] for v in fuera)


def test_los_estaticos_propios_se_sirven(web):
    for n, tipo in (("demo_den.js", "javascript"), ("demo_den.css", "css")):
        r = web.get(f"/estaticos/{n}")
        assert r.status_code == 200 and tipo in r.headers["content-type"] and len(r.text) > 500
    js = web.get("/estaticos/demo_den.js").text
    assert "innerHTML" not in js.replace("t.innerHTML = html", "")          # lo que viene del servidor se escribe con textContent
    assert "eval(" not in js and "Function(" not in js


def test_los_iconos_de_estado_que_usa_el_js_existen_en_el_sprite():
    sprite = (RAIZ / "front/app/estaticos/identidad.svg").read_text()
    js = (RAIZ / "front/app/estaticos/demo_den.js").read_text()
    usados = set(re.findall(r"'([a-z-]+)'", re.search(r"const ESTADOS = new Set\(\[(.*?)\]\)", js, re.S).group(1)))
    for e in usados:
        assert f'id="e-{e}"' in sprite and f'id="m-{e}"' in sprite, e
    for ley in ("karin", "datos", "penal"):
        assert f'id="l-{ley}"' in sprite
    assert 'id="n-ayuda"' in sprite


# ---- QA 2026-11-22: casos ajenos al corpus, leyes agrupadas, aviso sin JavaScript, rechazos con pantalla, notación de artículos ------------------------



def test_los_casos_ajenos_salen_del_banco_y_estan_marcados_fuera_del_corpus():
    """Los casos «fuera» son controles del banco de evaluación (ley «ninguna») que no tuvieron sugerencia con la cadena desplegada."""
    import json
    ruta = Path(__file__).resolve().parents[2] / "evaluacion/datos/denuncias_desarrollo_20261115_etiquetadas.json"
    if not ruta.exists():
        pytest.skip("el banco de evaluación no se versiona (tiene datos personales)")
    banco = {c["id"]: c for c in json.loads(ruta.read_text())["casos"]}
    fuera = [c for c in CASOS if c["tipo"] == "fuera"]
    assert len(fuera) >= 2
    for c in fuera:
        b = banco[c["banco"]]
        assert b["ley_principal"] == "ninguna" and c["texto"] == b["texto_original"], c["id"]
        assert c["articulos"] == () and c["fuera"] and esperado_ok(c), c["id"]


def esperado_ok(c):
    e = dd.esperado(c)
    return e["tipo"] == "fuera" and e["articulos"] == [] and e["fuera"] == c["fuera"]


def test_el_recordatorio_de_leyes_agrupa_las_normas_bajo_la_ley_karin():
    ctx = dd.contexto()
    por_tipo = {l["tipo"]: l for l in ctx["leyes"]}
    assert set(por_tipo) == {"karin", "datos", "penal"}
    inc = [(n["nombre"], n["numero"]) for n in por_tipo["karin"]["incluye"]]
    assert ("Código del Trabajo", "") in inc
    for numero in ("18.834", "18.883", "18.575"):
        assert any(n == numero for _, n in inc), numero
    assert not por_tipo["datos"]["incluye"] and not por_tipo["penal"]["incluye"]


def test_el_recordatorio_de_leyes_se_muestra_agrupado_y_no_dice_que_solo_hay_tres(web):
    t = web.get("/panel/demo?pestana=denuncias", headers=H).text
    sub = re.search(r'<ul class="den-sub".*?</ul>', t, re.S).group(0)
    for x in ("Código del Trabajo", "Estatuto Administrativo", "18.834", "Estatuto Administrativo municipal", "18.883", "18.575"):
        assert x in sub
    assert t.index('data-l="karin"') < t.index('<ul class="den-sub"') < t.index('data-l="datos"')      # la lista cuelga de la Ley Karin
    assert not re.search(r"solo (conoce|hay|tiene) (las )?(tres|3)", t, re.I)


def test_el_corpus_vigente_trae_las_normas_que_el_recordatorio_dice_incluir():
    if not CORPUS.exists():
        pytest.skip("el corpus vigente está fuera de git")
    corpus = CORPUS.read_text()
    for texto in ("Código del Trabajo", "Ley 18.834", "Ley 18.883", "Ley 18.575", "Ley 18.695", "Ley 19.628", "Ley 21.719", "Ley 20.393"):
        assert texto in corpus, texto


def test_sin_javascript_la_pestana_denuncias_avisa_en_vez_de_quedar_inerte(web):
    t = web.get("/panel/demo?pestana=denuncias", headers=H).text
    m = re.search(r"<noscript>(.*?)</noscript>", t, re.S)
    assert m and "JavaScript" in m.group(1) and 'class="cola-av s-warn' in m.group(1) and 'href="#e-revision-tiempo"' in m.group(1)
    assert ".den-b:not(:first-child){display:none}" in m.group(1)                  # los casos y el botón, inertes sin JS, no se ofrecen
    assert "Anonimizador" in m.group(1)                                              # y dice qué sí funciona


def test_un_rechazo_sin_pedir_json_responde_con_la_pantalla_de_error_de_kerna(web):
    d = {"csrf": "mal", "texto": CASO["texto"], "caso": CASO["id"]}
    for ruta, datos in (("/panel/demo/denuncia", d), ("/panel/clientes/crear", {"csrf": "mal", "id": "x", "nombre": "Y"})):
        r = web.post(ruta, headers={**H, "Accept": "text/html"}, data=datos)
        assert r.status_code == 403 and "text/html" in r.headers["content-type"], ruta
        assert "No pudimos confirmar tu solicitud" in r.text and '{"estado"' not in r.text, ruta
        assert r.headers["cache-control"] == "no-store"
        j = web.post(ruta, headers={**H, "Accept": "application/json"}, data=datos)                # con Accept JSON todo sigue igual
        assert j.status_code == 403 and j.json() == {"estado": "token"}, ruta
        o = web.post(ruta, headers={**H, "Accept": "text/html", "Origin": "https://otro.example"}, data=datos)
        assert o.status_code == 403 and "text/html" in o.headers["content-type"], ruta
    assert web.nucleo.casos == []


def test_sin_sesion_y_sin_pedir_json_tambien_es_una_pantalla(web):
    r = web.post("/panel/clientes/crear", headers={"Accept": "text/html"}, data={"csrf": _csrf(), "id": "x"})
    assert r.status_code == 401 and "text/html" in r.headers["content-type"] and '{"estado"' not in r.text
    assert web.post("/panel/clientes/crear", headers={"Accept": "application/json"}, data={"csrf": _csrf()}).json() == {"estado": "sesion"}


def test_el_articulo_obtenido_se_escribe_igual_que_el_esperado():
    for crudo, esperado_ in (("211 C", "211-C"), ("211-c", "211-C"), ("211-B bis", "211-B bis"), ("211 B bis", "211-B bis"), ("211-b-bis", "211-B bis"),
                             ("14 quinquies", "14 quinquies"), ("14-QUINQUIES", "14 quinquies"), ("16 BIS", "16 bis"), ("82", "82"), ("  211   A ", "211-A")):
        assert dd.articulo_normal(crudo) == esperado_, crudo
    r = dd.vista_resultado({"estado": "completada", "articulos": [art("207436-karin-art-211-c", "Código del Trabajo", "211 C", "confirma")]}, CASO)
    assert r["articulos"][0]["articulo"] == "211-C"
    assert "art. 211-C" in dict(CASO["articulos"])["207436-karin-art-211-c"]               # el esperado se escribe igual


def test_el_js_trae_los_avisos_con_icono_el_scroll_al_resultado_y_el_mensaje_de_credenciales():
    js = (RAIZ / "front/app/estaticos/demo_den.js").read_text()
    assert "prefers-reduced-motion" in js and "scrollIntoView" in js and "irAlResultado" in js
    assert "estado(ico || 'cadena-agotada', 40)" in js                                     # todo aviso lleva su ícono de estado
    assert "no aceptó las credenciales" in js and "no respondió" in js and "motivo === 'credenciales'" in js
    assert "Límite alcanzado" in js and "paste" in js
    css = (RAIZ / "front/app/estaticos/demo_den.css").read_text()
    assert "scroll-margin" in css
