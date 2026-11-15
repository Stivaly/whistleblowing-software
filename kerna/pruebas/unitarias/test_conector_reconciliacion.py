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


def pasada_c(v, n, e, con="Auditor2", t=1000.0):
    return ejecutar_pasada(v, n, e, "emp", ahora=lambda: t, compartir_con=con)


def test_compartir_todos_idempotente_y_nuevos(mundo):
    v, n, e = mundo
    v.agregar("c1"); v.agregar("c2")
    r = pasada_c(v, n, e)
    assert r.compartidos == 2 and sorted(c for c, _ in v.compartidos) == ["c1", "c2"]
    v.agregar("c3")
    r = pasada_c(v, n, e)
    assert r.compartidos == 1 and len(v.compartidos) == 3
    assert pasada_c(v, n, e).compartidos == 0 and len(v.compartidos) == 3


def test_compartir_no_repite_si_ya_tiene_acceso(mundo):
    v, n, e = mundo
    v.agregar("c1")["receivers"].append({"id": v.RECEPTOR_COMPARTIDO, "name": "Auditor2", "active": True})
    pasada_c(v, n, e)
    assert not getattr(v, "compartidos", [])


def test_compartir_desactivado_o_sin_permiso(mundo):
    v, n, e = mundo
    v.agregar("c1")
    pasada_c(v, n, e, con="")
    assert not getattr(v, "compartidos", [])
    v.sin_permiso_grant = True
    r = pasada_c(v, n, e)
    assert r.compartidos == 0 and not getattr(v, "compartidos", [])
    v.sin_permiso_grant = False
    assert pasada_c(v, n, e, t=2000.0).compartidos == 1


def test_compartir_receptor_inexistente(mundo):
    v, n, e = mundo
    v.agregar("c1")
    assert pasada_c(v, n, e, con="NoExiste").compartidos == 0


T0 = 1794312000.0 + 3600  # una hora después de generado_en de los resultados simulados
H = 3600.0


def pasada_t(v, n, e, t, **kw):
    return ejecutar_pasada(v, n, e, "emp", ahora=lambda: t, **kw)


def _agotar(n, ref):
    n.completar(ref, estado="revision_manual", motivo_revision="cadena_agotada", modo="manual", articulos=[])


def _caso_agotado(mundo):
    v, n, e = mundo
    v.agregar("c1", relato="Mi jefe me grita todos los días.")
    pasada(v, n, e)
    ref = next(iter(n.solicitudes))
    _agotar(n, ref)
    pasada(v, n, e)
    return v, n, e, ref


def test_reproceso_inmediato_cuenta_como_primer_reintento_y_publica(mundo):
    v, n, e, ref = _caso_agotado(mundo)
    r = pasada_t(v, n, e, T0, reprocesar=True)
    assert r.reenviados == 1 and len(n.solicitudes) == 2
    assert not any("\"c1\"" in c for c in n.cuerpos_enviados)
    nueva = [x for x in n.solicitudes if x != ref][0]
    n.completar(nueva)
    r = pasada_t(v, n, e, T0 + 1, reprocesar=True)
    assert r.reprocesados == 1
    assert [s.estado for s in v.notas_publicadas("kerna_sugerencia")] == ["revision_manual", "completada"]
    r = pasada_t(v, n, e, T0 + 99 * H, reprocesar=True)  # idempotente
    assert r.reenviados == 0 and len(n.solicitudes) == 2 and len(v.notas_publicadas("kerna_sugerencia")) == 2


def test_reintento_automatico_respeta_intervalo_y_maximo_3(mundo):
    v, n, e, ref = _caso_agotado(mundo)
    assert pasada_t(v, n, e, T0).reenviados == 0            # el fallo es reciente: aún no se reintenta
    assert pasada_t(v, n, e, T0 + 25 * H).reenviados == 1     # >24 h desde la nota: 1.er reintento
    for k in (1, 2, 3):
        refs = [x for x in n.solicitudes if x != ref and not n.solicitudes[x].get("estado") == "revision_manual"
                and n.solicitudes[x].get("estado") == "pendiente"]
        assert len(refs) == 1
        _agotar(n, refs[0])
        t = T0 + 25 * H + (k - 1) * 25 * H
        pasada_t(v, n, e, t + 1)                               # registra el fallo
        if k < 3:
            assert pasada_t(v, n, e, t + 23 * H).reenviados == 0   # menos de 24 h: espera
            assert pasada_t(v, n, e, t + 25 * H).reenviados == 1   # pasadas 24 h: siguiente
    assert len(n.solicitudes) == 4                              # original + 3 reintentos
    assert pasada_t(v, n, e, T0 + 999 * H).reenviados == 0      # tras el 3.º fallo queda en revisión manual
    assert len(n.solicitudes) == 4
    assert [s.estado for s in v.notas_publicadas("kerna_sugerencia")] == ["revision_manual"]


def test_reintentos_max_configurable(mundo):
    v, n, e, ref = _caso_agotado(mundo)
    pasada_t(v, n, e, T0, reintentos_max=1, reprocesar=True)
    nueva = [x for x in n.solicitudes if x != ref][0]
    _agotar(n, nueva)
    pasada_t(v, n, e, T0 + 1, reintentos_max=1)
    assert pasada_t(v, n, e, T0 + 50 * H, reintentos_max=1).reenviados == 0


def test_no_reintenta_decision_de_contenido_ni_completadas(mundo):
    v, n, e = mundo
    v.agregar("c1")
    v.agregar("c2", fecha="2026-11-01T11:00:00Z")
    pasada(v, n, e)
    refs = list(n.solicitudes)
    n.completar(refs[0], estado="revision_manual", motivo_revision="sin_normativa_aplicable", modo="manual", articulos=[])
    n.completar(refs[1])
    pasada(v, n, e)
    assert pasada_t(v, n, e, T0 + 99 * H, reprocesar=True).reenviados == 0
    assert len(n.solicitudes) == 2


def test_tope_de_envios_por_pasada_casos_nuevos(mundo):
    v, n, e = mundo
    for i in range(5):
        v.agregar("c%d" % i, fecha="2026-11-0%dT10:00:00Z" % (i + 1), relato="Hecho %d" % i)
    assert pasada_t(v, n, e, T0, envios_max=2).enviados == 2
    assert len(n.solicitudes) == 2
    assert pasada_t(v, n, e, T0 + 1, envios_max=2).enviados == 2   # los que no cupieron esperan, sin perderse
    assert pasada_t(v, n, e, T0 + 2, envios_max=2).enviados == 1
    assert len(n.solicitudes) == 5


def test_tope_de_envios_acota_reintentos_sin_consumir_intento(mundo):
    v, n, e = mundo
    for i in range(3):
        v.agregar("c%d" % i, fecha="2026-11-0%dT10:00:00Z" % (i + 1), relato="Hecho %d" % i)
    pasada_t(v, n, e, T0)
    for ref in list(n.solicitudes):
        _agotar(n, ref)
    pasada_t(v, n, e, T0 + 1)
    n0 = len(n.solicitudes)
    assert pasada_t(v, n, e, T0 + 25 * H, envios_max=1).reenviados == 1
    assert pasada_t(v, n, e, T0 + 25 * H + 1, envios_max=1).reenviados == 1
    assert pasada_t(v, n, e, T0 + 25 * H + 2, envios_max=1).reenviados == 1
    assert len(n.solicitudes) == n0 + 3


def test_envios_por_pasada_desde_entorno():
    from kerna_conector.config import _entero
    assert _entero(None, 5) == 5 and _entero("3", 5) == 3 and _entero("x", 5) == 5


def test_eventos_de_reintento_y_valoracion_sin_ids(mundo):
    from kerna_comun import telemetria
    visto = []
    telemetria.quitar_emisores()
    telemetria.registrar_emisor(lambda clase, nombre, valor, at: visto.append((nombre, dict(at))))
    try:
        v, n, e, ref = _caso_agotado(mundo)
        pasada_t(v, n, e, T0 + 25 * H)
    finally:
        telemetria.quitar_emisores()
    ev = next(a for nom, a in visto if nom == "conector_reintento")
    assert ev["intento"] == 1 and ev["motivo"] == "cadena_agotada" and "c1" not in str(ev)


def test_valoracion_del_auditor_sin_texto():
    from types import SimpleNamespace as S
    from kerna_conector.reconciliacion import _Pasada
    assert _Pasada._valoracion(S(tipo="feedback", nota=S(valoracion="arriba"))) == "util"
    assert _Pasada._valoracion(S(tipo="feedback", nota=S(valoracion="abajo"))) == "no_util"
    assert _Pasada._valoracion(S(tipo="clasificacion_auditor", nota=S(articulos=[]))) == "ninguno_aplica"


class C:  # corrida manual mínima
    id = "m1"
    inicio = T0


def _manual(v, n, e, t, en_vuelo_max=12, corrida=C):
    return ejecutar_pasada(v, n, e, "emp", ahora=lambda: t, corrida=corrida, en_vuelo_max=en_vuelo_max)


def test_corrida_manual_reintenta_todos_los_de_revision_manual_sin_importar_motivo(mundo):
    v, n, e = mundo
    for i, motivo in enumerate(["sin_normativa_aplicable", "validacion_fallida", "cadena_agotada"]):
        v.agregar("c%d" % i, fecha="2026-11-01T1%d:00:00Z" % i)
    v.agregar("ok", fecha="2026-11-02T10:00:00Z")
    pasada(v, n, e)
    refs = list(n.solicitudes)
    for ref, motivo in zip(refs[:3], ["sin_normativa_aplicable", "validacion_fallida", "cadena_agotada"]):
        n.completar(ref, estado="revision_manual", motivo_revision=motivo, modo="manual", articulos=[])
    n.completar(refs[3])
    pasada(v, n, e)
    assert pasada_t(v, n, e, T0 + 60, reprocesar=False).reenviados == 0   # el reintento automático no toca estos motivos
    r = _manual(v, n, e, T0 + 60)
    assert r.reenviados == 3 and len(n.solicitudes) == 7                  # la completada no se reenvía
    assert (r.manual_total, r.manual_fin, r.manual_en_vuelo, r.manual_completa) == (3, 0, 3, False)
    for x in [x for x in n.solicitudes if x not in refs]:
        n.completar(x)
    r = _manual(v, n, e, T0 + 120)
    assert (r.manual_total, r.manual_fin, r.manual_con, r.manual_en_vuelo, r.manual_completa) == (3, 3, 3, 0, True)
    assert r.reprocesados == 3
    r = _manual(v, n, e, T0 + 180)                                        # idempotente
    assert r.reenviados == 0 and len(n.solicitudes) == 7 and r.manual_completa
    assert len([s for s in v.notas_publicadas("kerna_sugerencia") if s.estado == "completada"]) == 4


def test_corrida_manual_respeta_el_tope_en_vuelo_y_avanza_por_turnos(mundo):
    v, n, e = mundo
    for i in range(5):
        v.agregar("c%d" % i, fecha="2026-11-01T1%d:00:00Z" % i)
    pasada(v, n, e)
    refs = list(n.solicitudes)
    for ref in refs:
        _agotar(n, ref)
    pasada(v, n, e)
    r = _manual(v, n, e, T0, en_vuelo_max=2)
    assert r.reenviados == 2 and r.manual_total == 5 and r.manual_en_vuelo == 2 and not r.manual_completa
    for x in [x for x in n.solicitudes if x not in refs]:
        n.completar(x)
    for t in range(1, 6):
        r = _manual(v, n, e, T0 + t, en_vuelo_max=2)
        for x in [x for x in n.solicitudes if x not in refs and "estado" not in n.solicitudes[x] or n.solicitudes[x].get("estado") == "pendiente"]:
            n.completar(x)
        if r.manual_completa:
            break
    assert r.manual_completa and r.manual_fin == 5 and r.manual_con == 5 and len(n.solicitudes) == 10


def test_corrida_manual_cuenta_los_que_siguen_sin_sugerencia(mundo):
    v, n, e, ref = _caso_agotado(mundo)
    _manual(v, n, e, T0)
    nueva = [x for x in n.solicitudes if x != ref][0]
    _agotar(n, nueva)
    r = _manual(v, n, e, T0 + 5)
    assert (r.manual_total, r.manual_fin, r.manual_con, r.manual_completa) == (1, 1, 0, True)
    assert [s.estado for s in v.notas_publicadas("kerna_sugerencia")] == ["revision_manual"]  # no duplica la nota


def test_corrida_manual_incluye_casos_sin_sugerencia_pendientes_y_con_error(mundo):
    v, n, e = mundo
    v.agregar("c1")
    v.agregar("c2", fecha="2026-11-02T10:00:00Z")
    pasada(v, n, e)                                   # c1 y c2 quedan pendientes en el núcleo
    r = _manual(v, n, e, T0)
    assert r.manual_total == 2 and r.manual_fin == 0 and not r.manual_completa
    for ref in list(n.solicitudes):
        n.completar(ref)
    r = _manual(v, n, e, T0 + 5)
    assert (r.manual_total, r.manual_fin, r.manual_con, r.manual_completa) == (2, 2, 2, True)


def test_corrida_manual_sin_nada_que_reintentar_termina_de_inmediato(mundo):
    v, n, e = mundo
    v.agregar("c1")
    n.completar_al_enviar = True
    pasada(v, n, e)
    pasada(v, n, e)
    r = _manual(v, n, e, T0)
    assert r.manual_completa and r.manual_total == 0 and r.reenviados == 0


def test_resultado_se_rellena_y_alimenta_el_estado_en_vivo(mundo):
    v, n, e, ref = _caso_agotado(mundo)
    assert e.contar_objetos("resultado", "actual", "revision_manual", prefijo_nota=True) == 1
    assert e.contar_estados() == {"completado": 1}


def test_corrida_retomable_tras_reinicio_del_conector(mundo):
    v, n, e, ref = _caso_agotado(mundo)
    _manual(v, n, e, T0)
    e2 = e                                              # el estado persiste: otra instancia de pasada = reinicio
    r = _manual(v, n, e2, T0 + 5)
    assert r.reenviados == 0 and len(n.solicitudes) == 2 and r.manual_en_vuelo == 1


class TablaFalsa:
    def __init__(self):
        self.filas = {}

    def get_entity(self, pk, rk):
        if rk not in self.filas:
            raise type("ResourceNotFoundError", (Exception,), {})()
        return dict(self.filas[rk])

    def upsert_entity(self, ent, mode="merge"):
        self.filas[ent["RowKey"]] = {**self.filas.get(ent["RowKey"], {}), **ent}


def test_solicitud_manual_se_toma_avanza_y_se_cierra_con_resultado():
    from kerna_conector.solicitudes import SolicitudReintento
    t = TablaFalsa()
    reloj = [T0]
    s = SolicitudReintento(t, ahora=lambda: reloj[0])
    assert s.activa() is None and not s.pedida()                    # sin fila
    t.filas["solicitud"] = {"estado": "solicitado", "solicitado_en": "2026-11-13T03:00:00Z"}
    c = s.activa()
    f = t.filas["solicitud"]
    assert c.id.startswith("m") and f["estado"] == "en_curso" and f["inicio"] and f["solicitado_en"]
    assert s.activa().id == c.id                                    # sigue la misma corrida
    reloj[0] += 100
    s.progreso(c, total=10, enviados=6, resueltos=4, con=3, en_vuelo=2)
    f = t.filas["solicitud"]
    assert (f["total"], f["resueltos"], f["con_sugerencia"], f["sin_sugerencia"], f["en_vuelo"]) == (10, 4, 3, 1, 2)
    assert f["eta_s"] == 150 and f["estado"] == "en_curso"
    reloj[0] += 150
    s.terminar(c, total=10, resueltos=10, con=8)
    f = t.filas["solicitud"]
    assert f["estado"] == "atendido" and f["reintentados"] == 10 and f["con_sugerencia"] == 8 and f["sin_sugerencia"] == 2
    assert f["fin"] and f["atendido_en"] and f["incompleto"] is False and s.activa() is None
    assert not SolicitudReintento(None).pedida() and SolicitudReintento(None).activa() is None
    SolicitudReintento(None).terminar(c)


def test_corrida_atascada_se_cierra_tras_dos_horas():
    from kerna_conector.solicitudes import SolicitudReintento
    t = TablaFalsa()
    reloj = [T0]
    s = SolicitudReintento(t, ahora=lambda: reloj[0])
    t.filas["solicitud"] = {"estado": "solicitado"}
    s.activa()
    reloj[0] += 7300
    assert s.activa() is None
    assert t.filas["solicitud"]["estado"] == "atendido" and t.filas["solicitud"]["incompleto"] is True


def test_solicitar_desde_el_conector_no_pisa_una_corrida_en_curso():
    from kerna_conector.solicitudes import SolicitudReintento
    t = TablaFalsa()
    s = SolicitudReintento(t)
    assert s.solicitar("ajustes") and t.filas["solicitud"]["estado"] == "solicitado" and t.filas["solicitud"]["origen"] == "ajustes"
    assert not s.solicitar("ajustes")
    s.publicar_vivo({"casos": 3})
    assert t.filas["conector"]["casos"] == 3 and t.filas["conector"]["actualizado_en"]


def _cfg():
    from kerna_conector.config import Config
    return Config("http://v", "u", "p", "http://k", "i", "s")


def test_ajustes_del_panel_se_aplican_y_los_invalidos_se_ignoran():
    from kerna_conector.ajustes import parametros
    base = parametros(_cfg(), None)
    assert (base.envios_max, base.reintentos_max, base.reintento_horas, base.intervalo_s, base.de_ajustes) == (5, 3, 24.0, 30.0, False)
    fila = {"valores": json.dumps({"envios": 8, "reintentos": 0, "espera": 12, "revision": 60, "reprocesar": True,
                                   "evaluador": False, "candidatos": 7}), "actualizado_en": "2026-11-13T03:00:00Z"}
    p = parametros(_cfg(), fila)
    assert (p.envios_max, p.reintentos_max, p.reintento_horas, p.intervalo_s) == (8, 0, 12.0, 60.0)
    assert p.reprocesar_marca == "2026-11-13T03:00:00Z" and p.de_ajustes
    malo = {"valores": json.dumps({"envios": 99, "reintentos": "x", "espera": 0, "revision": 1, "reprocesar": "si"})}
    p = parametros(_cfg(), malo)
    assert (p.envios_max, p.reintentos_max, p.reintento_horas, p.intervalo_s, p.reprocesar_marca) == (5, 3, 24.0, 30.0, None)
    assert parametros(_cfg(), {"valores": "no es json"}) == base


def test_ajuste_reprocesar_pide_una_corrida_por_guardado(tmp_path):
    from kerna_conector import __main__ as m
    from kerna_conector.ajustes import LectorAjustes
    from kerna_conector.solicitudes import SolicitudReintento
    ajustes, reint = TablaFalsa(), TablaFalsa()
    ajustes.filas["actual"] = {"valores": json.dumps({"reprocesar": True}), "actualizado_en": "2026-11-13T03:00:00Z"}
    s, la, e = SolicitudReintento(reint), LectorAjustes(ajustes), est.EstadoSqlite(":memory:")
    p = m.parametros(_cfg(), la.leer())
    assert p.reprocesar_marca and not e.objeto_procesado("_ajustes", "reprocesar", p.reprocesar_marca)


def test_estado_en_vivo_de_la_pasada(mundo):
    from kerna_conector import __main__ as m
    v, n, e, ref = _caso_agotado(mundo)
    r = pasada(v, n, e)
    vivo = m._vivo(e, r, m.parametros(_cfg(), None), False)
    assert vivo["completado"] == 1 and vivo["en_revision_manual"] == 1 and vivo["resultado_desconocido"] == 0
    assert vivo["intervalo_s"] == 30 and "reprocesar" in vivo["ajustes_aplicados"] and vivo["en_reintento"] is False


def test_estado_en_vivo_publica_pendientes_por_motivo(mundo):
    import json
    from kerna_conector import __main__ as m
    v, n, e, ref = _caso_agotado(mundo)
    r = pasada(v, n, e)
    vivo = m._vivo(e, r, m.parametros(_cfg(), None), False)
    d = json.loads(vivo["pendientes_por_motivo"])
    assert sum(d.values()) == vivo["en_revision_manual"] + vivo["error"] and d  # la suma cuadra con el total pendiente
    e.fijar_procesado("x1", "resultado", "actual", "revision_manual|validacion_fallida")
    e.fijar_procesado("x2", "resultado", "actual", "revision_manual")
    assert e.contar_motivos_revision().get("validacion_fallida") == 1 and e.contar_motivos_revision().get("sin_motivo") == 1


def test_estado_en_vivo_cuenta_casos_por_modo_de_su_sugerencia_final():
    e = est.EstadoSqlite(":memory:")
    for caso, modo in (("a", "oficial"), ("b", "oficial"), ("c", "respaldo"), ("d", None)):
        e.fijar_procesado(caso, "resultado", "actual", "completada")
        if modo:
            e.fijar_procesado(caso, "modo", "actual", modo)
    e.fijar_procesado("m", "resultado", "actual", "revision_manual|cadena_agotada")
    e.fijar_procesado("m", "modo", "actual", "manual")
    assert e.contar_modos() == {"oficial": 2, "respaldo": 1, "desconocido": 1}


def test_sql_de_motivos_no_lleva_porcentaje_literal():
    """PostgreSQL (psycopg) toma `%` como marcador: el patrón LIKE debe ir como parámetro."""
    e = est.EstadoSqlite(":memory:")
    vistas = []
    original = e._ejecutar
    e._ejecutar = lambda sql, params=(), lectura=False: (vistas.append(sql), original(sql, params, lectura))[1]
    e.contar_motivos_revision()
    assert vistas and all("%" not in q for q in vistas)


def test_casos_que_ya_no_existen_en_veridy_se_archivan_y_no_cuentan(mundo):
    from kerna_conector import __main__ as m
    v, n, e, ref = _caso_agotado(mundo)
    v.agregar("fantasma", fecha="2026-10-02T00:00:00Z")
    pasada(v, n, e)
    assert sum(e.contar_estados().values()) == 2 and e.contar_archivados() == 0
    del v.casos["fantasma"]  # el caso se borró en Veridy
    r = pasada(v, n, e)
    assert r.archivados == 1 and e.contar_archivados() == 1
    assert e.obtener("fantasma") is not None  # la fila se conserva
    vivo = m._vivo(e, r, m.parametros(_cfg(), None), False)
    assert vivo["casos"] == 1 and vivo["archivados"] == 1
    assert sum(e.contar_estados().values()) == 1 and "pendiente" not in e.contar_estados()
    assert vivo["completado"] <= vivo["casos"] and vivo["resultado_desconocido"] == 0
    assert pasada(v, n, e).archivados == 0  # idempotente


def test_caso_archivado_que_reaparece_se_reactiva_y_lista_vacia_no_archiva(mundo):
    v, n, e = mundo
    v.agregar("c1")
    pasada(v, n, e)
    guardado = v.casos.pop("c1")
    assert pasada(v, n, e).archivados == 0 and e.contar_archivados() == 0  # lista vacía = fallo de lectura
    v.agregar("c2")
    assert pasada(v, n, e).archivados == 1
    v.casos["c1"] = guardado
    r = pasada(v, n, e)
    assert r.reactivados == 1 and e.contar_archivados() == 0
