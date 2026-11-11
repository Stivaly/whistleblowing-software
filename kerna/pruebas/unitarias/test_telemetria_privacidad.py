"""Privacidad de la telemetría: solo salen atributos permitidos y textos cortos; las métricas solo usan dimensiones
de baja cardinalidad. Sin red: el SDK de Azure Monitor se reemplaza por dobles."""
import logging
import sys
import types

import pytest

from kerna_comun import telemetria, telemetria_azure

pytestmark = [pytest.mark.rnf("RNF-privacidad")]

TEXTO_DENUNCIA = "El jefe de la sucursal me acosó durante meses y nadie hizo nada " * 3  # > 64 caracteres


@pytest.fixture(autouse=True)
def limpio():
    telemetria.quitar_emisores()
    yield
    telemetria.quitar_emisores()


def test_filtrar_descarta_atributos_fuera_de_la_lista():
    sal = telemetria.filtrar({"texto": "hola", "consulta": "acoso", "prompt": "x", "nombre": "Ana", "modo": "oficial",
                              "duracion_ms": 12, "json_valido": True, "tokens_entrada": 3})
    assert sal == {"modo": "oficial", "duracion_ms": 12, "json_valido": True, "tokens_entrada": 3}


def test_filtrar_descarta_textos_largos_y_valores_no_escalares():
    assert len(TEXTO_DENUNCIA) > telemetria.MAX_TEXTO
    sal = telemetria.filtrar({"motivo": TEXTO_DENUNCIA, "codigo": "x" * 64, "estado": "x" * 65,
                              "modelo": ["a"], "proveedor": {"k": "v"}, "cliente": None, "tipo": b"bytes"})
    assert sal == {"codigo": "x" * 64}  # 64 caracteres es el máximo permitido


def test_ningun_emisor_recibe_el_texto_de_una_denuncia():
    visto = []
    telemetria.registrar_emisor(lambda clase, nombre, valor, at: visto.append((clase, nombre, valor, dict(at))))
    telemetria.evento("e", motivo=TEXTO_DENUNCIA, texto=TEXTO_DENUNCIA, estado="completada")
    telemetria.contador("c", 1, consulta=TEXTO_DENUNCIA, codigo="500")
    with telemetria.etapa("generacion", prompt=TEXTO_DENUNCIA, modelo="gemini") as a:
        a["respuesta"] = TEXTO_DENUNCIA
    assert visto and all(set(at) <= telemetria.ATRIBUTOS_PERMITIDOS for *_, at in visto)
    assert TEXTO_DENUNCIA not in repr(visto) and "acosó" not in repr(visto)


def test_dimensiones_de_metricas_son_un_subconjunto_de_los_permitidos_sin_identificadores():
    dim = telemetria_azure.DIMENSIONES
    assert dim <= telemetria.ATRIBUTOS_PERMITIDOS
    # identificadores y valores continuos nunca son dimensiones (cardinalidad y rastreo de casos)
    assert not dim & {"id_solicitud", "ref_opaca", "duracion_ms", "tokens_entrada", "tokens_salida", "intento",
                      "version_corpus", "articulos", "citas_rechazadas", "casos", "fragmentos"}


def test_azure_solo_usa_dimensiones_permitidas(monkeypatch):
    registros, histograma, contadores = [], [], []

    class Instrumento:
        def __init__(self, lista, nombre=None):
            self.lista, self.nombre = lista, nombre

        def record(self, valor, dims):
            self.lista.append((valor, dict(dims)))

        def add(self, valor, dims):
            self.lista.append((self.nombre, valor, dict(dims)))

    class Medidor:
        def create_histogram(self, nombre, unit=None):
            return Instrumento(histograma, nombre)

        def create_counter(self, nombre):
            return Instrumento(contadores, nombre)

    def modulo(nombre, **attrs):
        m = types.ModuleType(nombre)
        m.__dict__.update(attrs)
        return m

    fakes = {
        "azure": modulo("azure"), "azure.monitor": modulo("azure.monitor"),
        "azure.monitor.opentelemetry": modulo("azure.monitor.opentelemetry",
                                              configure_azure_monitor=lambda **kw: None),
        "opentelemetry": modulo("opentelemetry", metrics=types.SimpleNamespace(get_meter=lambda n: Medidor())),
        "opentelemetry.sdk": modulo("opentelemetry.sdk"),
        "opentelemetry.sdk.resources": modulo("opentelemetry.sdk.resources",
                                              Resource=types.SimpleNamespace(create=lambda d: d)),
    }
    for nombre, m in fakes.items():
        monkeypatch.setitem(sys.modules, nombre, m)
    monkeypatch.setattr(telemetria_azure, "_activo", False)

    class Captura(logging.Handler):
        def emit(self, rec):
            registros.append(rec)

    log = logging.getLogger(telemetria_azure.LOGGER)
    h = Captura()
    log.addHandler(h)
    try:
        telemetria_azure.activar("kerna-prueba")
        telemetria.contador("conector_caso_enviado", ref_opaca="4838c958-498b-47b7-b1f3-a72e24c58824", codigo="500")
        with telemetria.etapa("recuperacion", id_solicitud="abc", modo="oficial", fragmentos=8,
                              prompt=TEXTO_DENUNCIA, recuperacion="nube"):
            pass
        telemetria.evento("solicitud_terminada", id_solicitud="abc", motivo=TEXTO_DENUNCIA, estado="completada")
    finally:
        log.removeHandler(h)
        telemetria.quitar_emisores()

    assert contadores == [("kerna.conector_caso_enviado", 1, {"codigo": "500"})]  # ref_opaca no es dimensión
    assert len(histograma) == 1
    dims = histograma[0][1]
    assert dims == {"etapa": "recuperacion", "modo": "oficial", "recuperacion": "nube"}
    assert set(dims) <= telemetria_azure.DIMENSIONES
    # los registros (AppTraces) solo llevan atributos permitidos más "clase", y nunca el texto
    assert len(registros) == 2
    for r in registros:
        extra = {k for k in vars(r) if k in telemetria.ATRIBUTOS_PERMITIDOS | {"clase"}}
        assert "prompt" not in vars(r) and TEXTO_DENUNCIA not in r.getMessage() + repr(vars(r))
        assert extra <= telemetria.ATRIBUTOS_PERMITIDOS | {"clase"}
    assert any(getattr(r, "id_solicitud", None) == "abc" for r in registros)
    assert not any(hasattr(r, "motivo") for r in registros if r.getMessage() == "solicitud_terminada")  # texto largo
