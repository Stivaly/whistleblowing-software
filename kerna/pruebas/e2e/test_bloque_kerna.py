"""Indicador y bloque de Kerna en la vista del caso del auditor (cliente Angular de Veridy).

Cada prueba fuerza el estado interceptando con `page.route` la respuesta de `GET /api/recipient/rtips/<id>` e inyectando
comentarios de Kerna simulados (y, si hace falta, una cuenta "Kerna AI" entre los destinatarios del caso). Así no depende
del conector ni del núcleo y no escribe nada en Veridy: los envíos (POST de comentarios) también se interceptan.

Variables: VERIDY_URL, VERIDY_USUARIO y VERIDY_PASSWORD (destinatario que vea al menos un caso). Para la prueba del
denunciante, además VERIDY_RECIBO (recibo de una denuncia de prueba). Se omiten con motivo claro si falta alguna, si el
usuario no ve casos o si la instancia desplegada aún no trae el bloque de Kerna. NO se ejecutan contra Azure sin que la
usuaria lo pida (el despliegue actual no trae este código). Los textos son los de kerna/docs/diseno/textos-finales.md.
"""
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from playwright.sync_api import TimeoutError as TiempoAgotado

pytestmark = [pytest.mark.e2e, pytest.mark.pr("PR-13"), pytest.mark.pr("PR-16")]

ID_KERNA = "kerna-simulada-0001"
NOMBRE_KERNA = "Kerna AI (cuenta de servicio simulada)"
ID_AUDITOR_SIM = "auditor-simulado-0002"


# ---------------------------------------------------------------- constructores de notas simuladas
def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _articulo(i: int, norma: str = "Ley N.° 21.643") -> dict:
    return {
        "id_sugerencia": f"s-{i}", "id_articulo": f"a-{i}", "norma": norma, "articulo": f"Artículo {i}",
        "explicacion": f"Explicación de ejemplo {i}.", "cita": f"Cita literal de ejemplo {i}.",
        "enlace_fuente": "https://www.bcn.cl/leychile/navegar?idNorma=1", "confianza": round(0.9 - i / 10, 2),
    }


def _sugerencia(ahora: datetime, **extra) -> dict:
    base = {
        "tipo": "kerna_sugerencia", "version": 1, "id_solicitud": "sol-e2e-123", "version_corpus": 1, "estado": "completada",
        "motivo_revision": None, "modo": "oficial", "recuperacion": "nube", "contingencia": False,
        "generado_en": _iso(ahora - timedelta(minutes=1)),
        "articulos": [_articulo(1), _articulo(2), _articulo(3, "Ley N.° 20.393")],
    }
    base.update(extra)
    return base


def _revision(ahora: datetime, motivo: str) -> dict:
    return _sugerencia(ahora, estado="revision_manual", motivo_revision=motivo, modo="manual", articulos=[])


def _estado(ahora: datetime, estado: str, hace_min: float) -> dict:
    return {"tipo": "kerna_estado", "version": 1, "estado": estado, "fecha": _iso(ahora - timedelta(minutes=hace_min)),
            "id_seguimiento": "seg-e2e-9"}


def _clasificacion() -> dict:
    return {"tipo": "kerna_clasificacion", "version": 1, "observacion": "Prueba",
            "articulos": [{"id_articulo": "a-1", "origen": "sugerido"}, {"id_articulo": "Otra norma, art. 5", "origen": "agregado_por_auditor"}]}


# Estado -> (nombre, edad del caso en minutos o None, notas [(autor, nota)], etiqueta esperada, fragmento del mensaje del panel)
def _casos(ahora: datetime):
    k, a = "kerna", "auditor"
    return [
        ("sin-info", 1, [], "Sin información de Kerna", "Aún no hay información de Kerna para este caso."),
        ("generando", 3, [(k, _estado(ahora, "en_proceso", 1))], "Preparando sugerencia", "Kerna recibió el caso y está buscando"),
        ("lista", 3, [(k, _sugerencia(ahora))], "Sugerencia lista", None),
        ("contingencia", 3, [(k, _sugerencia(ahora, modo="respaldo", contingencia=True))], "Sugerencia lista · modo alternativo",
         "Esta sugerencia se preparó con un modelo alternativo"),
        ("contingencia", 3, [(k, _sugerencia(ahora, modo="local", contingencia=True))], "Sugerencia lista · modo alternativo",
         "Esta sugerencia se preparó con un modelo alternativo"),
        ("contingencia", 3, [(k, _sugerencia(ahora, recuperacion="local", contingencia=True))], "Sugerencia lista · búsqueda alternativa",
         "las normas se buscaron con un método alternativo"),
        ("revision-tiempo", 3, [(k, _revision(ahora, "tiempo_agotado"))], "Sin sugerencia · tiempo excedido", "Kerna tardó más de lo permitido"),
        ("revision-citas", 3, [(k, _revision(ahora, "validacion_fallida"))], "Sin sugerencia · citas no verificadas",
         "sus citas no coincidían con el texto vigente"),
        ("sin-normativa", 3, [(k, _revision(ahora, "sin_normativa_aplicable"))], "Sin normativa encontrada", "Kerna no encontró, entre las normas que conoce"),
        ("cadena-agotada", 3, [(k, _revision(ahora, "cadena_agotada"))], "Sin sugerencia · no se pudo generar", "por una falla propia"),
        ("nucleo-no-disponible", 3, [(k, _estado(ahora, "nucleo_no_disponible", 1))], "Kerna no disponible", "Kerna no está disponible en este momento."),
        ("conector-inactivo", 12, [], "Kerna sin respuesta", "Kerna todavía no ha recibido este caso"),
        ("conector-inactivo", 20, [(k, _estado(ahora, "en_proceso", 12))], "Kerna sin respuesta", "Kerna recibió este caso, pero la sugerencia no ha llegado"),
        ("valorada", 3, [(k, _sugerencia(ahora)), (a, _clasificacion())], "Clasificación guardada", "Tu clasificación de este caso quedó guardada"),
    ]


def _id_caso(caso) -> str:
    nombre, _edad, notas, _et, _msg = caso
    if nombre == "contingencia":
        s = notas[0][1]
        return "contingencia-" + ("busqueda-local" if s["recuperacion"] == "local" else s["modo"])
    if nombre == "conector-inactivo" and notas:
        return "conector-inactivo-en-proceso"
    return nombre


CASOS = _casos(datetime.now(timezone.utc))


# ---------------------------------------------------------------- utilidades de página
def _instalar_simulacion(pagina, edad_min, notas, cuenta_kerna=True):
    """Intercepta el GET del caso e inyecta la cuenta de Kerna y las notas simuladas; deja pasar lo demás."""
    def manejar(ruta):
        if ruta.request.method != "GET":
            ruta.fallback()
            return
        resp = ruta.fetch()
        datos = resp.json()
        ahora = datetime.now(timezone.utc)
        # La instancia puede tener ya la cuenta y notas reales de Kerna: se retiran para que mande la simulación.
        reales = {r.get("id") for r in datos.get("receivers", []) if (r.get("name") or "").strip().lower().startswith("kerna")}
        receptores = [r for r in datos.get("receivers", [])
                      if r.get("id") not in (ID_KERNA, ID_AUDITOR_SIM) and r.get("id") not in reales]
        if cuenta_kerna:
            receptores.append({"id": ID_KERNA, "name": NOMBRE_KERNA, "active": True})
        receptores.append({"id": ID_AUDITOR_SIM, "name": "Auditor simulado", "active": True})
        datos["receivers"] = receptores
        if edad_min is not None:
            datos["creation_date"] = _iso(ahora - timedelta(minutes=edad_min))
        comentarios = [c for c in datos.get("comments", [])
                       if c.get("author_id") not in (ID_KERNA, ID_AUDITOR_SIM) and c.get("author_id") not in reales
                       and '"tipo": "kerna_' not in (c.get("content") or "") and '"tipo":"kerna_' not in (c.get("content") or "")]
        for i, (autor, nota) in enumerate(notas):
            comentarios.append({
                "id": str(uuid.uuid4()), "creation_date": _iso(ahora - timedelta(seconds=90 - i)),
                "content": json.dumps(nota, ensure_ascii=False), "author_id": ID_KERNA if autor == "kerna" else ID_AUDITOR_SIM,
                "visibility": "internal", "type": None, "data": None,
            })
        datos["comments"] = comentarios
        ruta.fulfill(response=resp, json=datos)

    pagina.route(re.compile(r".*/api/recipient/rtips/[^/?]+$"), manejar)


@pytest.fixture
def caso_abierto(pagina, url_veridy, credenciales):
    """Inicia sesión como destinatario y devuelve una función que abre su primer caso con una simulación dada."""
    usuario, clave = credenciales
    pagina.goto(url_veridy + "/#/login", wait_until="domcontentloaded")
    pagina.fill("[name=username]", usuario)
    pagina.fill("[name=password]", clave)
    pagina.click("#login-button")
    pagina.wait_for_function("!location.hash.includes('/login')", timeout=60_000)
    pagina.goto(url_veridy + "/#/recipient/reports", wait_until="domcontentloaded")
    try:
        pagina.wait_for_selector("tr.tip-action-open", timeout=20_000)
    except TiempoAgotado:
        pytest.skip("el usuario de prueba no ve ningún caso (hace falta uno para abrir la vista del caso)")
    pagina.locator("tr.tip-action-open").first.click()
    pagina.wait_for_function("/reports\\/[^/]+/.test(location.hash)")
    id_caso = re.search(r"reports/([^/?#]+)", pagina.evaluate("location.hash")).group(1)

    def abrir(edad_min=3, notas=(), cuenta_kerna=True, esperar=True):
        pagina.unroute_all()
        _instalar_simulacion(pagina, edad_min, list(notas), cuenta_kerna)
        # Sin recargar: Veridy guarda la sesión en memoria y una recarga la cierra. Se vuelve a la lista y se
        # entra otra vez al caso para que la vista lo pida de nuevo (ya con la simulación instalada).
        pagina.evaluate("location.hash = '#/recipient/reports'")
        pagina.wait_for_selector("tr.tip-action-open", timeout=30_000)
        pagina.evaluate(f"location.hash = '#/reports/{id_caso}'")
        if esperar:
            try:
                pagina.wait_for_selector("#kerna-indicador", timeout=45_000)
            except TiempoAgotado:
                pytest.fail("no apareció #kerna-indicador en 45 s (instancia sin el bloque de Kerna o caso sin cargar)")
        return id_caso

    return abrir


def _indicador(pagina):
    return pagina.locator("#kerna-indicador")


# ---------------------------------------------------------------- una prueba por estado (y variante)
@pytest.mark.cu("CU-01")
@pytest.mark.parametrize("caso", CASOS, ids=[_id_caso(c) for c in CASOS])
def test_estado_del_indicador(pagina, caso_abierto, caso):
    nombre, edad, notas, etiqueta, fragmento = caso
    caso_abierto(edad, notas)
    ind = _indicador(pagina)
    assert ind.get_attribute("data-estado") == nombre
    assert etiqueta in ind.inner_text()
    ind.click()
    panel = pagina.locator("#kerna-panel")
    panel.wait_for(state="visible")
    # aviso permanente en todos los estados
    assert "no es un dictamen jurídico" in panel.inner_text()
    if fragmento:
        assert fragmento in panel.inner_text()
    if nombre in ("lista", "contingencia", "valorada"):
        assert panel.locator("[data-cy=kerna-articulo]").count() == 3
        assert "Ver el artículo en la Biblioteca del Congreso Nacional" in panel.inner_text()
        assert "sol-e2e-123" in panel.inner_text()  # código de seguimiento para reportar un problema
    else:
        assert panel.locator("[data-cy=kerna-articulo]").count() == 0
    if nombre == "contingencia":
        assert panel.locator("[data-cy=kerna-aviso-contingencia]").count() == 1
    # el trabajo manual nunca se bloquea: el cambio de estado del caso sigue disponible
    assert pagina.locator("#tip-action-change-status, #actionsDropdown").count() >= 1
    # nada de jerga técnica en pantalla
    texto = panel.inner_text() + ind.inner_text()
    for prohibida in ("timeout", "HTTP", "Gemini", "Voyage", "Qdrant", "Azure"):
        assert prohibida not in texto


@pytest.mark.cu("CU-01")
def test_estado_sin_conexion(pagina, caso_abierto):
    caso_abierto(3, [("kerna", _sugerencia(datetime.now(timezone.utc)))])
    assert _indicador(pagina).get_attribute("data-estado") == "lista"
    pagina.evaluate("window.dispatchEvent(new Event('offline'))")
    pagina.wait_for_function("document.querySelector('#kerna-indicador').dataset.estado === 'sin-conexion'")
    assert "Sin conexión" in _indicador(pagina).inner_text()
    _indicador(pagina).click()
    panel = pagina.locator("#kerna-panel")
    assert "se perdió la conexión con la plataforma" in panel.inner_text()
    assert panel.locator("[data-cy=kerna-reintentar]").count() == 1
    # los controles de escritura se deshabilitan; lo ya mostrado sigue a la vista
    assert panel.locator("[data-cy=kerna-guardar-clasificacion]").is_disabled()


@pytest.mark.cu("CU-01")
def test_sin_cuenta_de_kerna_no_hay_indicador(pagina, caso_abierto):
    caso_abierto(3, [("kerna", _sugerencia(datetime.now(timezone.utc)))])  # control positivo: el bloque existe
    caso_abierto(3, [("kerna", _sugerencia(datetime.now(timezone.utc)))], cuenta_kerna=False, esperar=False)
    pagina.wait_for_timeout(1500)
    assert pagina.locator("#kerna-indicador").count() == 0
    assert pagina.locator("#kerna-panel").count() == 0


# ---------------------------------------------------------------- tooltip y accesibilidad
@pytest.mark.pr("PR-17")
def test_tooltip_hover_foco_esc_y_persistencia(pagina, caso_abierto):
    caso_abierto(3, [("kerna", _sugerencia(datetime.now(timezone.utc)))])
    ind, tt = _indicador(pagina), pagina.locator("#kerna-tooltip")
    assert ind.get_attribute("aria-describedby") == "kerna-tooltip"
    assert tt.get_attribute("role") == "tooltip"
    assert not tt.is_visible()
    ind.hover()
    tt.wait_for(state="visible")
    texto = tt.inner_text()
    assert "Ley N.° 21.643 · 3 artículos" in texto and "Modo habitual" in texto
    assert "Abre el detalle con clic o Enter. Esc cierra este aviso." in texto
    tt.hover()  # persistente: el puntero puede pasar sobre el tooltip sin que se cierre
    pagina.wait_for_timeout(600)
    assert tt.is_visible()
    pagina.keyboard.press("Escape")  # descartable
    pagina.wait_for_timeout(150)
    assert not tt.is_visible()
    pagina.mouse.move(5, 5)
    pagina.wait_for_timeout(500)
    # con el teclado: el foco en el indicador (programático o con Tab) muestra el tooltip
    ind.focus()
    tt.wait_for(state="visible")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(150)
    assert not tt.is_visible()
    assert pagina.evaluate("document.activeElement.id") == "kerna-indicador"  # Esc no mueve el foco
    pagina.keyboard.press("Enter")  # Enter abre el panel
    pagina.locator("#kerna-panel").wait_for(state="visible")
    assert ind.get_attribute("aria-expanded") == "true"


@pytest.mark.pr("PR-17")
def test_animacion_de_espera_respeta_reduced_motion(pagina, caso_abierto):
    caso_abierto(3, [("kerna", _estado(datetime.now(timezone.utc), "en_proceso", 1))])
    assert _indicador(pagina).evaluate("e => getComputedStyle(e).animationName") == "kerna-pulso"
    pagina.emulate_media(reduced_motion="reduce")
    assert _indicador(pagina).evaluate("e => getComputedStyle(e).animationName") == "none"


# ---------------------------------------------------------------- notas JSON fuera del hilo de comentarios
@pytest.mark.pr("PR-17")
def test_las_notas_json_no_se_muestran_como_texto_crudo(pagina, caso_abierto):
    ahora = datetime.now(timezone.utc)
    caso_abierto(3, [("kerna", _estado(ahora, "en_proceso", 2)), ("kerna", _sugerencia(ahora)), ("auditor", _clasificacion())])
    pestanas = pagina.locator("ul.nav-tabs button")
    for i in range(pestanas.count()):
        pestanas.nth(i).click()
        pagina.wait_for_timeout(300)
        cuerpo = pagina.inner_text("body")
        assert "kerna_sugerencia" not in cuerpo and "kerna_estado" not in cuerpo and "kerna_clasificacion" not in cuerpo


# ---------------------------------------------------------------- valoración y clasificación (sin escribir: se interceptan los POST)
@pytest.mark.pr("PR-18")
@pytest.mark.cu("CU-03")
@pytest.mark.cu("CU-04")
def test_valoracion_y_clasificacion_se_envian_como_notas_internas(pagina, caso_abierto):
    id_caso = caso_abierto(3, [("kerna", _sugerencia(datetime.now(timezone.utc)))])
    enviados = []

    def capturar(ruta):
        enviados.append(json.loads(ruta.request.post_data))
        cuerpo = enviados[-1]
        ruta.fulfill(json={"id": str(uuid.uuid4()), "creation_date": _iso(datetime.now(timezone.utc)), "content": cuerpo["content"],
                           "author_id": ID_AUDITOR_SIM, "visibility": cuerpo["visibility"], "type": None, "data": None})

    pagina.route(re.compile(rf".*/api/recipient/rtips/{re.escape(id_caso)}/comments$"), capturar)
    _indicador(pagina).click()
    panel = pagina.locator("#kerna-panel")
    panel.wait_for(state="visible")
    # valoración del primer artículo con observación
    panel.locator("[data-cy=kerna-voto-abajo]").first.click()
    panel.locator("#kerna-obs-s-1").fill("No corresponde a los hechos")
    panel.locator("[data-cy=kerna-enviar-valoracion]").click()
    assert len(enviados) == 1 and enviados[0]["visibility"] == "internal"
    nota = json.loads(enviados[0]["content"])
    assert nota == {"tipo": "kerna_feedback", "version": 1, "id_sugerencia": "s-1", "valoracion": "abajo",
                    "observacion": "No corresponde a los hechos"}
    # clasificación: un artículo sugerido y uno agregado
    panel.locator(".kerna-casilla input").first.check()
    panel.locator("#kerna-otro").fill("Otra norma, art. 5")
    panel.locator("#kerna-otro").press("Enter")
    panel.locator("[data-cy=kerna-guardar-clasificacion]").click()
    pagina.wait_for_timeout(500)
    assert len(enviados) == 2 and enviados[1]["visibility"] == "internal"
    nota = json.loads(enviados[1]["content"])
    assert nota["tipo"] == "kerna_clasificacion" and nota["version"] == 1
    assert nota["articulos"] == [{"id_articulo": "a-1", "origen": "sugerido"},
                                 {"id_articulo": "Otra norma, art. 5", "origen": "agregado_por_auditor"}]


# ---------------------------------------------------------------- el denunciante no ve nada de Kerna
@pytest.mark.pr("PR-17")
def test_el_denunciante_no_ve_nada_de_kerna(pagina, url_veridy):
    recibo = os.environ.get("VERIDY_RECIBO")
    if not recibo:
        pytest.skip("falta VERIDY_RECIBO (recibo de una denuncia de prueba para entrar como denunciante)")
    pagina.goto(url_veridy + "/", wait_until="domcontentloaded")
    pagina.fill("[name=receipt]", recibo)
    pagina.click("#ReceiptButton")
    pagina.wait_for_load_state("networkidle", timeout=60_000)
    pagina.wait_for_timeout(1500)
    for selector in ("#kerna-indicador", "#kerna-panel", "src-kerna-indicador", "src-kerna-panel", "[data-cy=kerna-tooltip]"):
        assert pagina.locator(selector).count() == 0, selector
    cuerpo = pagina.inner_text("body").lower()
    assert "kerna" not in cuerpo
