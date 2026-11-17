"""Ajustes `compartir` y `alerta` del conector: parámetros, compartir con varios equipos y casos sin sugerencia."""
import json

import pytest
from conector_apoyo import NucleoFalso, VeridyFalso

from kerna_conector import estado as est
from kerna_conector.ajustes import APLICADOS, nombres_receptores, parametros
from kerna_conector.config import Config
from kerna_conector.reconciliacion import ejecutar_pasada


def cfg(**kw):
    return Config(veridy_url="http://v", veridy_usuario="u", veridy_password="p", kerna_api_url="http://n",
                  kerna_client_id="c", kerna_client_secret="s", **kw)


def fila(**v):
    return {"valores": json.dumps(v), "actualizado_en": "2026-11-17T10:00:00Z"}


def test_aplicados_incluye_compartir_y_alerta():
    assert set(APLICADOS) == {"envios", "reintentos", "espera", "revision", "reprocesar", "compartir", "alerta"}


def test_parametros_alerta_y_compartir():
    p = parametros(cfg(), None)
    assert p.alerta_h == 6 and p.equipos is None
    p = parametros(cfg(), fila(alerta=1, compartir=["analista", "comite"]))
    assert p.alerta_h == 1 and p.equipos == ("analista", "comite") and p.de_ajustes
    assert parametros(cfg(), fila(alerta=24)).alerta_h == 24
    for malo in (5, True, "6", None):
        assert parametros(cfg(), fila(alerta=malo)).alerta_h == 6
    assert parametros(cfg(), fila(compartir=["legal", "inventado"])).equipos == ("legal",)
    assert parametros(cfg(), fila(compartir=[])).equipos == ()
    assert parametros(cfg(), fila(envios=3)).equipos is None   # sin llave: rige el entorno
    assert parametros(cfg(), fila(compartir="legal")).equipos is None


def test_nombres_receptores_y_anulacion_por_entorno():
    assert nombres_receptores(("analista", "comite", "auditoria", "legal"), {}) == (
        "Auditor Kerna", "kerna-equipo-comite", "kerna-equipo-auditoria", "kerna-equipo-legal")
    assert nombres_receptores(("analista", "x"), {}) == ("Auditor Kerna",)
    assert nombres_receptores((), {}) == ()
    assert nombres_receptores(("legal",), {"KERNA_EQUIPOS_RECEPTOR": json.dumps({"legal": "otra-cuenta"})}) == ("otra-cuenta",)
    assert nombres_receptores(("legal",), {"KERNA_EQUIPOS_RECEPTOR": "no json"}) == ("kerna-equipo-legal",)


class VeridyEquipos(VeridyFalso):
    IDS = {"auditor kerna": "id-analista", "kerna-equipo-comite": "id-comite", "kerna-equipo-legal": "id-legal"}

    def buscar_receptor(self, nombre):
        return self.IDS.get(nombre.casefold())

    def compartir_caso(self, id_caso, id_receptor):
        if getattr(self, "sin_permiso_grant", False):
            from kerna_conector.veridy import CasoNoAccesible
            raise CasoNoAccesible("403", 403)
        self.compartidos = getattr(self, "compartidos", [])
        self.compartidos.append((id_caso, id_receptor))
        self.casos[id_caso]["receivers"].append({"id": id_receptor, "name": id_receptor, "active": True})


@pytest.fixture
def mundo():
    return VeridyEquipos(), NucleoFalso(), est.EstadoSqlite(":memory:")


def pasada(v, n, e, con, t=1000.0):
    return ejecutar_pasada(v, n, e, "emp", ahora=lambda: t, compartir_con=con)


def test_compartir_con_varios_equipos_una_vez_cada_uno(mundo):
    v, n, e = mundo
    v.agregar("c1"); v.agregar("c2")
    con = ("Auditor Kerna", "kerna-equipo-comite")
    r = pasada(v, n, e, con)
    assert r.compartidos == 4 and sorted(v.compartidos) == [("c1", "id-analista"), ("c1", "id-comite"), ("c2", "id-analista"), ("c2", "id-comite")]
    assert r.equipos_sin_cuenta == ()
    assert pasada(v, n, e, con).compartidos == 0 and len(v.compartidos) == 4
    v.agregar("c3")
    assert pasada(v, n, e, con).compartidos == 2
    # un equipo agregado después recibe lo ya existente; quitar uno no revoca lo compartido
    r = pasada(v, n, e, ("kerna-equipo-legal",))
    assert r.compartidos == 3 and len(v.compartidos) == 9


def test_equipo_sin_cuenta_no_bloquea_a_los_otros_y_se_informa(mundo):
    v, n, e = mundo
    v.agregar("c1")
    r = pasada(v, n, e, ("kerna-equipo-auditoria", "Auditor Kerna"))
    assert r.compartidos == 1 and v.compartidos == [("c1", "id-analista")]
    assert r.equipos_sin_cuenta == ("kerna-equipo-auditoria",)


def test_lista_vacia_no_comparte_y_un_str_sigue_valiendo(mundo):
    v, n, e = mundo
    v.agregar("c1")
    assert pasada(v, n, e, ()).compartidos == 0 and not getattr(v, "compartidos", [])
    assert pasada(v, n, e, "").compartidos == 0
    assert pasada(v, n, e, "Auditor Kerna").compartidos == 1


def test_403_bloquea_todo_el_compartir_de_la_pasada(mundo):
    v, n, e = mundo
    v.agregar("c1"); v.agregar("c2")
    v.sin_permiso_grant = True
    r = pasada(v, n, e, ("Auditor Kerna", "kerna-equipo-comite"))
    assert r.compartidos == 0 and not getattr(v, "compartidos", [])
    v.sin_permiso_grant = False
    assert pasada(v, n, e, ("Auditor Kerna", "kerna-equipo-comite"), t=2000.0).compartidos == 4


def test_no_comparte_con_la_cuenta_propia(mundo):
    v, n, e = mundo
    v.IDS = {"auditor kerna": v.id_usuario}
    v.agregar("c1")
    assert pasada(v, n, e, ("Auditor Kerna",)).compartidos == 0


# ---- contar_sin_sugerencia_antes
def _caso(e, id_caso, creado, estado=None, resultado=None):
    e.registrar(id_caso, "ref-" + id_caso)
    e._ejecutar("UPDATE correspondencia_caso SET creado_en = ? WHERE id_caso = ?", (creado, id_caso))
    if estado:
        e.actualizar(id_caso, estado=estado)
    if resultado:
        e.fijar_procesado(id_caso, "resultado", "actual", resultado)


def test_contar_sin_sugerencia_antes():
    e = est.EstadoSqlite(":memory:")
    viejo, nuevo, limite = "2026-11-17T01:00:00Z", "2026-11-17T09:00:00Z", "2026-11-17T06:00:00Z"
    _caso(e, "n", viejo)                                                       # nuevo, viejo: cuenta
    _caso(e, "p", viejo, est.PENDIENTE)                                        # pendiente: cuenta
    _caso(e, "x", viejo, est.ERROR)                                            # error: cuenta
    _caso(e, "rm", viejo, est.COMPLETADO, "revision_manual|cadena_agotada")    # revisión manual: cuenta
    _caso(e, "ok", viejo, est.COMPLETADO, "completada")                        # con sugerencia: no
    _caso(e, "r", nuevo, est.ERROR)                                            # reciente: no
    _caso(e, "ar", viejo, est.ERROR)                                           # archivado: no
    e.fijar_procesado("ar", *est.ARCHIVO, "1")
    assert e.contar_sin_sugerencia_antes(limite) == 4
    assert e.contar_sin_sugerencia_antes("2026-11-17T00:00:00Z") == 0
    assert e.contar_sin_sugerencia_antes("2026-11-17T23:00:00Z") == 5


def test_fila_en_vivo_publica_alerta_y_equipos():
    from types import SimpleNamespace

    from kerna_conector.__main__ import _vivo
    from kerna_conector.reconciliacion import ResultadoPasada
    e = est.EstadoSqlite(":memory:")
    e.registrar("c", "ref-c")
    e._ejecutar("UPDATE correspondencia_caso SET creado_en = '2000-01-01T00:00:00Z' WHERE id_caso = 'c'")
    p = parametros(cfg(), fila(alerta=1, compartir=["analista", "comite"]))
    r = ResultadoPasada(equipos_sin_cuenta=("kerna-equipo-comite",))
    f = _vivo(e, r, p, False)
    assert f["sin_sugerencia_alerta"] == 1 and f["alerta_h"] == 1
    assert f["equipos"] == "analista,comite" and f["equipos_sin_cuenta"] == "kerna-equipo-comite"
    assert "compartir" in f["ajustes_aplicados"] and "alerta" in f["ajustes_aplicados"]
