"""Pruebas de la pasada de reconciliación con Veridy y núcleo simulados (sin red)."""
import json
import threading

import pytest
from conector_apoyo import AUDITOR, CUENTA, NucleoFalso, OTRO_AUDITOR, VeridyFalso

from kerna_comun import notas
from kerna_conector import estado as est
from kerna_conector.reconciliacion import ejecutar_pasada

pr = lambda x: pytest.mark.pr(x)  # noqa: E731


def pasada(v, n, e, t=1000.0):
    return ejecutar_pasada(v, n, e, "emp", ahora=lambda: t)


@pytest.fixture
def mundo():
    return VeridyFalso(), NucleoFalso(), est.EstadoSqlite(":memory:")


@pr("PR-13")
def test_caso_nuevo_flujo_completo(mundo):
    v, n, e = mundo
    v.agregar("caso1", relato="Mi jefe Juan Pérez me acosa. Escríbeme a ana@correo.cl")
    r = pasada(v, n, e)
    assert r.enviados == 1 and n.envios_de_caso == 1
    ref, texto = json.loads(n.cuerpos_enviados[0])
    assert ref != "caso1" and "caso1" not in n.cuerpos_enviados[0]
    assert "ana@correo.cl" not in texto and "[CORREO_1]" in texto
    assert "Describa los hechos" in texto and "Acoso laboral" in texto and "Oficina central" in texto
    estados = v.notas_publicadas("kerna_estado")
    assert [x.estado for x in estados] == ["en_proceso"]
    assert estados[0].id_seguimiento.startswith("sol-")
    assert not v.notas_publicadas("kerna_sugerencia")
    n.completar(ref)
    pasada(v, n, e)
    sug = v.notas_publicadas("kerna_sugerencia")
    assert len(sug) == 1 and sug[0].articulos[0].id_articulo == "ley21643-art2"
    assert all(c["visibility"] == "internal" for c in v.casos["caso1"]["comments"])
    assert e.obtener("caso1").estado == est.COMPLETADO


@pr("PR-18")
def test_nota_conserva_modo_y_contingencia(mundo):
    v, n, e = mundo
    v.agregar("c")
    pasada(v, n, e)
    ref = next(iter(n.solicitudes))
    n.completar(ref, modo="local", recuperacion="local", contingencia=True)
    pasada(v, n, e)
    s = v.notas_publicadas("kerna_sugerencia")[0]
    assert (s.modo, s.recuperacion, s.contingencia) == ("local", "local", True)
    assert s.version_corpus == 7 and s.id_solicitud.startswith("sol-")


@pr("PR-14")
@pr("PR-36")
def test_casos_previos_se_procesan_una_vez_y_sin_duplicar(tmp_path, mundo):
    v, n, _ = mundo
    n.completar_al_enviar = True
    for i in range(5):
        v.agregar("c%d" % i, fecha="2026-10-0%dT10:00:00Z" % (i + 1))
    ruta = str(tmp_path / "e.db")
    e = est.EstadoSqlite(ruta)
    pasada(v, n, e)
    pasada(v, n, e)
    assert n.envios_de_caso == 5
    for _ in range(3):  # reinicios con estado persistente
        e.cerrar()
        e = est.EstadoSqlite(ruta)
        pasada(v, n, e)
    assert n.envios_de_caso == 5
    assert len(v.notas_publicadas("kerna_estado")) == 5
    assert len(v.notas_publicadas("kerna_sugerencia")) == 5


@pr("PR-14")
def test_orden_por_fecha_de_creacion(mundo):
    v, n, e = mundo
    v.agregar("nuevo", fecha="2026-11-05T10:00:00Z", relato="B")
    v.agregar("viejo", fecha="2026-01-01T10:00:00Z", relato="A")
    pasada(v, n, e)
    assert json.loads(n.cuerpos_enviados[0])[1].startswith("Describa los hechos: A") and json.loads(n.cuerpos_enviados[1])[1].startswith("Describa los hechos: B")


@pr("PR-36")
def test_estado_perdido_tras_publicar_no_duplica_notas(mundo):
    v, n, e = mundo
    v.agregar("c")
    pasada(v, n, e)
    ref = next(iter(n.solicitudes))
    n.completar(ref)
    pasada(v, n, e)
    assert len(v.notas_publicadas("kerna_sugerencia")) == 1
    n.completar_al_enviar = True
    e2 = est.EstadoSqlite(":memory:")  # estado perdido por completo
    pasada(v, n, e2)
    pasada(v, n, e2)
    assert len(v.notas_publicadas("kerna_sugerencia")) == 1
    assert len(v.notas_publicadas("kerna_estado")) == 1


@pr("PR-36")
def test_se_cae_entre_publicar_y_guardar_el_id(mundo):
    v, n, e = mundo
    v.agregar("c")
    pasada(v, n, e)
    ref = next(iter(n.solicitudes))
    n.completar(ref)
    original = e.marcar_procesado

    def falla(*a, **k):
        if a[1] == "sugerencia":
            raise RuntimeError("caída")
        return original(*a, **k)
    e.marcar_procesado = falla
    r = pasada(v, n, e)
    assert r.errores == 1 and len(v.notas_publicadas("kerna_sugerencia")) == 1
    e.marcar_procesado = original
    pasada(v, n, e)
    pasada(v, n, e)
    assert len(v.notas_publicadas("kerna_sugerencia")) == 1
    assert e.obtener("c").estado == est.COMPLETADO and e.obtener("c").id_nota_sugerencia


@pr("PR-39")
def test_solicitud_completada_sin_nota_se_publica_una_vez(mundo):
    v, n, e = mundo
    v.agregar("c")
    pasada(v, n, e)
    assert not v.notas_publicadas("kerna_sugerencia")
    n.completar(next(iter(n.solicitudes)))
    for _ in range(3):
        pasada(v, n, e)
    assert len(v.notas_publicadas("kerna_sugerencia")) == 1


@pr("PR-31")
def test_pasadas_concurrentes_no_duplican(mundo):
    v, n, e = mundo
    n.completar_al_enviar = True
    for i in range(4):
        v.agregar("c%d" % i, fecha="2026-10-0%dT00:00:00Z" % (i + 1))
    dentro, liberar = threading.Event(), threading.Event()
    original = v.listar_casos
    primera = []

    def listar():
        if not primera:  # la primera pasada se detiene a mitad hasta que la segunda haya intentado correr
            primera.append(1)
            dentro.set()
            assert liberar.wait(timeout=5)
        return original()
    v.listar_casos = listar
    resultados = []
    h1 = threading.Thread(target=lambda: resultados.append(pasada(v, n, e)))
    h1.start()
    assert dentro.wait(timeout=5)
    h2 = threading.Thread(target=lambda: resultados.append(pasada(v, n, e)))
    h2.start()
    h2.join()
    liberar.set()
    h1.join()
    assert sorted(r.omitida for r in resultados) == [False, True]
    pasada(v, n, e)
    assert n.envios_de_caso == 4
    assert len(v.notas_publicadas("kerna_estado")) == 4
    assert len(v.notas_publicadas("kerna_sugerencia")) == 4


@pr("PR-31")
def test_cerrojo_omite_pasada_en_curso(mundo):
    v, n, e = mundo
    assert e.tomar_cerrojo("pasada", "otro", 1000.0, 900)
    r = pasada(v, n, e)
    assert r.omitida
    assert pasada(v, n, e, t=3000.0).omitida is False  # el cerrojo vencido se recupera


def _sugerencia_lista(v, n, e):
    v.agregar("c")
    pasada(v, n, e)
    ref = next(iter(n.solicitudes))
    n.completar(ref)
    pasada(v, n, e)
    return ref


@pr("PR-16")
def test_feedback_y_clasificacion_validos_en_orden_y_una_vez(mundo):
    v, n, e = mundo
    _sugerencia_lista(v, n, e)
    ida = v.notas_publicadas("kerna_sugerencia")[0].articulos[0].id_sugerencia
    idf = v.comentar("c", AUDITOR, {"tipo": "kerna_feedback", "version": 1, "id_sugerencia": ida,
                                    "valoracion": "arriba", "observacion": "Bien, lo vio Pedro Soto"},
                     fecha="2026-11-03T10:00:00Z")
    idc = v.comentar("c", OTRO_AUDITOR, {"tipo": "kerna_clasificacion", "version": 1, "observacion": "ok",
                                         "articulos": [{"id_articulo": "ley21643-art2", "origen": "sugerido"}]},
                     fecha="2026-11-03T11:00:00Z")
    # inválidas: denunciante (sin autor), pública, personal, de la propia cuenta
    v.comentar("c", None, {"tipo": "kerna_feedback", "version": 1, "id_sugerencia": ida, "valoracion": "abajo"})
    v.comentar("c", AUDITOR, {"tipo": "kerna_feedback", "version": 1, "id_sugerencia": ida, "valoracion": "abajo"},
               visibilidad="public")
    v.comentar("c", AUDITOR, {"tipo": "kerna_clasificacion", "version": 1, "articulos": []}, visibilidad="personal")
    v.comentar("c", CUENTA, {"tipo": "kerna_feedback", "version": 1, "id_sugerencia": ida, "valoracion": "abajo"})
    v.comentar("c", AUDITOR, "nota común de un auditor")
    for _ in range(3):
        pasada(v, n, e)
    assert [d[:2] for d in n.decisiones] == [("feedback", idf), ("clasificacion", idc)]
    assert n.decisiones[0][3] == "arriba" and "Pedro Soto" not in str(n.decisiones[0][4])
    assert n.decisiones[1][2] == [{"id_articulo": "ley21643-art2", "origen": "sugerido"}]


@pr("PR-16")
def test_vale_la_ultima_valoracion_de_cada_sugerencia(mundo):
    v, n, e = mundo
    _sugerencia_lista(v, n, e)
    for val, f in (("arriba", "2026-11-03T10:00:00Z"), ("abajo", "2026-11-03T11:00:00Z")):
        v.comentar("c", AUDITOR, {"tipo": "kerna_feedback", "version": 1, "id_sugerencia": "s1", "valoracion": val},
                   fecha=f)
    pasada(v, n, e)
    assert [d[3] for d in n.decisiones] == ["abajo"]


@pr("PR-24")
def test_identificadores_no_llegan_al_nucleo(mundo):
    v, n, e = mundo
    v.agregar("id-real-del-caso-123", relato="Me acosa Juan Pérez, RUT 12.345.678-5, correo jp@empresa.cl",
              lugar="Calle Falsa 123", )
    _sugerencia_lista_aparte = pasada(v, n, e)
    ref = next(iter(n.solicitudes))
    n.completar(ref)
    pasada(v, n, e)
    ida = v.notas_publicadas("kerna_sugerencia")[0].articulos[0].id_sugerencia
    v.comentar("id-real-del-caso-123", AUDITOR,
               {"tipo": "kerna_feedback", "version": 1, "id_sugerencia": ida, "valoracion": "abajo",
                "observacion": "Escribir a maria@correo.cl, RUT 9.876.543-2"})
    pasada(v, n, e)
    todo = "\n".join(n.cuerpos_enviados)
    for secreto in ("12.345.678-5", "jp@empresa.cl", "maria@correo.cl", "9.876.543-2", "id-real-del-caso-123",
                    "Camila", "Rojas", "foto-secreta", "etiqueta secreta", "Nombre completo"):
        assert secreto not in todo
    assert len(n.decisiones) == 1


@pr("PR-24")
def test_el_estado_guarda_el_id_real_y_la_ref(mundo):
    v, n, e = mundo
    v.agregar("id-real")
    pasada(v, n, e)
    c = e.obtener("id-real")
    assert c.ref_opaca in n.solicitudes and c.ref_opaca != "id-real"


def test_nucleo_caido_publica_aviso_una_vez_y_se_recupera(mundo):
    v, n, e = mundo
    n.caido = True
    v.agregar("c1", fecha="2026-10-01T00:00:00Z")
    v.agregar("c2", fecha="2026-10-02T00:00:00Z")
    r = pasada(v, n, e)
    assert r.nucleo_caido and not r.exitosa
    pasada(v, n, e)
    avisos = v.notas_publicadas("kerna_estado")
    assert [a.estado for a in avisos] == ["nucleo_no_disponible"] * 2
    assert n.envios_de_caso == 0
    n.caido = False
    r = pasada(v, n, e)
    assert r.exitosa and n.envios_de_caso == 2
    assert [a.estado for a in v.notas_publicadas("kerna_estado")].count("en_proceso") == 2
    for ref in list(n.solicitudes):
        n.completar(ref)
    pasada(v, n, e)
    assert len(v.notas_publicadas("kerna_sugerencia")) == 2


def test_nucleo_cae_con_caso_pendiente(mundo):
    v, n, e = mundo
    v.agregar("c")
    pasada(v, n, e)
    n.caido = True
    pasada(v, n, e)
    pasada(v, n, e)
    assert [a.estado for a in v.notas_publicadas("kerna_estado")] == ["en_proceso", "nucleo_no_disponible"]
    n.caido = False
    n.completar(next(iter(n.solicitudes)))
    assert pasada(v, n, e).exitosa
    assert len(v.notas_publicadas("kerna_sugerencia")) == 1


def test_caso_inaccesible_o_ilegible_no_detiene_la_pasada_y_se_reintenta_con_espera(mundo):
    v, n, e = mundo
    v.agregar("malo", fecha="2026-10-01T00:00:00Z")
    v.agregar("basura", fecha="2026-10-02T00:00:00Z")
    v.agregar("bueno", fecha="2026-10-03T00:00:00Z")
    v.sin_acceso.add("malo")
    v.ilegibles.add("basura")
    r = pasada(v, n, e, t=1000.0)
    assert r.errores == 2 and r.enviados == 1
    assert e.obtener("malo").estado == est.ERROR and e.obtener("malo").intentos == 1
    pasada(v, n, e, t=1001.0)  # aún dentro de la espera
    assert e.obtener("malo").intentos == 1
    pasada(v, n, e, t=1100.0)
    assert e.obtener("malo").intentos == 2
    assert e.obtener("malo").proximo_intento - 1100.0 == 60
    v.sin_acceso.clear()
    pasada(v, n, e, t=1300.0)
    assert e.obtener("malo").estado == est.PENDIENTE
    assert n.envios_de_caso == 2


def test_ejecucion_registrada(mundo):
    v, n, e = mundo
    v.agregar("c")
    pasada(v, n, e)
    ej = e.ejecuciones()[0]
    assert ej["casos"] == 1 and ej["enviados"] == 1 and ej["fin"]


def test_publicacion_siempre_interna(mundo):
    v, n, e = mundo
    v.agregar("c")
    pasada(v, n, e)
    assert v.casos["c"]["comments"] and all(c["visibility"] == "internal" for c in v.casos["c"]["comments"])
    assert isinstance(notas.leer(v.casos["c"]["comments"][0]["content"]), notas.Estado)
