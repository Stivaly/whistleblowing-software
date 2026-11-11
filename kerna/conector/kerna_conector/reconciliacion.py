"""Una pasada de reconciliación: pura y probable, con Veridy, núcleo y estado inyectados.

Privacidad: el texto del caso solo vive en variables locales de la pasada; no va a disco, a registros ni a
telemetría. El identificador real del caso solo llega al `estado`; al núcleo solo va la `ref_opaca`.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from kerna_comun import telemetria
from kerna_comun.anonimizador import anonimizar

from . import estado as est
from . import lector_casos, lector_decisiones, publicador
from .nucleo import ErrorNucleo, NucleoNoDisponible
from .veridy import CasoNoAccesible, ErrorVeridy

log = logging.getLogger("kerna.conector")

MAX_TEXTO = 60_000
CERROJO = "pasada"
TTL_CERROJO_S = 900


@dataclass
class ResultadoPasada:
    casos: int = 0
    enviados: int = 0
    sugerencias: int = 0
    estados: int = 0
    decisiones: int = 0
    errores: int = 0
    nucleo_caido: bool = False
    omitida: bool = False
    resultado: str = "ok"

    @property
    def exitosa(self) -> bool:
        return not (self.errores or self.nucleo_caido)


class _Pasada:
    def __init__(self, veridy, nucleo, estado: est.Estado, id_empresa: str, ahora: Callable[[], float]):
        self.v, self.n, self.e, self.ahora = veridy, nucleo, estado, ahora
        self.id_empresa = id_empresa
        self.r = ResultadoPasada()
        self.id_cuenta = veridy.id_usuario

    # ---- publicación idempotente --------------------------------------------------------------------------
    def _publicar_una_vez(self, id_caso: str, tipo: str, clave: str, caso: dict, hay_propia, armar) -> Optional[str]:
        """Publica una nota solo si no hay constancia de que ya exista. `hay_propia(caso)` devuelve el id de una
        nota equivalente de la cuenta de servicio ya presente en el caso (se adopta); `armar()` el contenido."""
        if self.e.objeto_procesado(id_caso, tipo, clave):
            return self.e.id_nota_procesado(id_caso, tipo, clave)
        existente = hay_propia(caso)
        if existente:
            self.e.marcar_procesado(id_caso, tipo, clave, existente)
            return existente
        creada = self.v.publicar_nota(id_caso, armar())
        id_nota = str(creada.get("id") or "")
        self.e.marcar_procesado(id_caso, tipo, clave, id_nota)
        return id_nota

    def _publicar_estado(self, id_caso: str, caso: dict, nuevo: str, id_seguimiento: Optional[str]) -> None:
        def propia(c):
            for n in lector_casos.notas_de_cuenta(c, self.id_cuenta, "kerna_estado"):
                if n.nota.estado == nuevo:
                    return n.id_nota
            return None

        antes = self.e.objeto_procesado(id_caso, "estado", nuevo)
        self._publicar_una_vez(id_caso, "estado", nuevo, caso, propia,
                               lambda: publicador.contenido(publicador.armar_estado(nuevo, id_seguimiento)))
        if not antes:
            self.r.estados += 1

    def _llamar(self, funcion, *args):
        """Llama al núcleo; si ya falló en esta pasada no insiste (se reintentará en la siguiente)."""
        if self.r.nucleo_caido:
            raise NucleoNoDisponible("el núcleo ya no respondió en esta pasada")
        return funcion(*args)

    def _fallo(self, id_caso: str, codigo: str) -> None:
        self.e.registrar_fallo(id_caso, codigo, self.ahora())
        self.r.errores += 1
        telemetria.contador("conector_fallo_caso", codigo=codigo)
        log.warning("caso con error: %s", codigo)

    def _nucleo_caido(self, id_caso: str, caso: dict, id_seguimiento: Optional[str]) -> None:
        self.r.nucleo_caido = True
        self._publicar_estado(id_caso, caso, "nucleo_no_disponible", id_seguimiento)

    # ---- etapas por caso ----------------------------------------------------------------------------------
    def _debido(self, corr: est.Correspondencia) -> bool:
        return corr.proximo_intento <= self.ahora()

    def procesar(self, meta: dict) -> None:
        id_caso = str(meta["id"])
        corr = self.e.obtener(id_caso) or self.e.registrar(id_caso, str(uuid.uuid4()))
        if not self._debido(corr):
            return
        if corr.estado in (est.NUEVO, est.ERROR):
            self._nuevo(meta, corr)
        elif corr.estado == est.PENDIENTE:
            self._pendiente(corr)
        elif corr.estado == est.COMPLETADO:
            self._decisiones(corr)

    def _leer(self, id_caso: str, meta: Optional[dict] = None) -> Optional[dict]:
        if meta is not None and meta.get("accessible") is False:
            self._fallo(id_caso, "sin_acceso")
            return None
        try:
            return self.v.leer_caso(id_caso)
        except CasoNoAccesible as exc:
            self._fallo(id_caso, "http_%s" % exc.codigo)
        except ErrorVeridy as exc:
            self._fallo(id_caso, "veridy_%s" % (exc.codigo or "red"))
        except Exception as exc:  # caso ilegible: no detiene la pasada
            self._fallo(id_caso, "ilegible_" + type(exc).__name__)
        return None

    def _nuevo(self, meta: dict, corr: est.Correspondencia) -> None:
        id_caso = corr.id_caso
        caso = self._leer(id_caso, meta)
        if caso is None:
            self.e.actualizar(id_caso, estado=est.ERROR)
            return
        # Sugerencia ya publicada antes de que el estado supiera del caso (estado perdido): se adopta.
        previa = lector_casos.notas_de_cuenta(caso, self.id_cuenta, "kerna_sugerencia")
        if previa:
            self.e.marcar_procesado(id_caso, "sugerencia", "unica", previa[0].id_nota)
            self.e.actualizar(id_caso, estado=est.COMPLETADO, id_nota_sugerencia=previa[0].id_nota,
                              id_solicitud=previa[0].nota.id_solicitud, intentos=0, proximo_intento=0, ultimo_error=None)
            return
        try:
            relato = lector_casos.extraer_relato(caso)
        except Exception as exc:
            self._fallo(id_caso, "ilegible_" + type(exc).__name__)
            self.e.actualizar(id_caso, estado=est.ERROR)
            return
        if not relato.strip():
            self._fallo(id_caso, "sin_texto")
            self.e.actualizar(id_caso, estado=est.ERROR)
            return
        texto = anonimizar(relato).texto[:MAX_TEXTO]
        del relato
        try:
            resp = self._llamar(self.n.enviar_caso, corr.ref_opaca, texto)
        except NucleoNoDisponible:
            self._nucleo_caido(id_caso, caso, None)
            self.e.actualizar(id_caso, estado=est.NUEVO)
            return
        except ErrorNucleo as exc:
            self._fallo(id_caso, "nucleo_%s" % exc.codigo)
            self.e.actualizar(id_caso, estado=est.ERROR)
            return
        finally:
            del texto
        id_solicitud = resp.get("id_solicitud")
        self.e.actualizar(id_caso, estado=est.PENDIENTE, id_solicitud=id_solicitud, intentos=0,
                          proximo_intento=0, ultimo_error=None)
        self.r.enviados += 1
        telemetria.contador("conector_caso_enviado", ref_opaca=corr.ref_opaca)
        self._publicar_estado(id_caso, caso, "en_proceso", id_solicitud)

    def _pendiente(self, corr: est.Correspondencia) -> None:
        id_caso = corr.id_caso
        try:
            res = self._llamar(self.n.consultar_sugerencia, corr.ref_opaca)
        except NucleoNoDisponible:
            self.r.nucleo_caido = True
            if not self.e.objeto_procesado(id_caso, "estado", "nucleo_no_disponible"):
                caso = self._leer(id_caso)
                if caso is not None:
                    self._nucleo_caido(id_caso, caso, corr.id_solicitud)
            return
        except ErrorNucleo as exc:
            self._fallo(id_caso, "nucleo_%s" % exc.codigo)
            return
        if res is None:  # el núcleo no conoce la solicitud: se reenvía con la misma ref_opaca
            self.e.actualizar(id_caso, estado=est.NUEVO)
            return
        if res.get("estado") not in ("completada", "revision_manual"):
            return
        caso = self._leer(id_caso)
        if caso is None:
            return
        ya = self.e.objeto_procesado(id_caso, "sugerencia", "unica")
        id_nota = self._publicar_una_vez(
            id_caso, "sugerencia", "unica", caso, self._sugerencia_propia,
            lambda: publicador.contenido(publicador.armar_sugerencia(res)))
        if not ya:
            self.r.sugerencias += 1
        self.e.actualizar(id_caso, estado=est.COMPLETADO, id_nota_sugerencia=id_nota,
                          id_solicitud=res.get("id_solicitud") or corr.id_solicitud,
                          intentos=0, proximo_intento=0, ultimo_error=None)

    def _sugerencia_propia(self, caso: dict) -> Optional[str]:
        propias = lector_casos.notas_de_cuenta(caso, self.id_cuenta, "kerna_sugerencia")
        return propias[0].id_nota if propias else None

    def _decisiones(self, corr: est.Correspondencia) -> None:
        id_caso = corr.id_caso
        caso = self._leer(id_caso)
        if caso is None:
            return
        for d in lector_decisiones.extraer(caso, self.id_cuenta):
            if self.e.objeto_procesado(id_caso, d.tipo, d.id_nota):
                continue
            try:
                if d.tipo == "feedback":
                    ok = self._llamar(self.n.enviar_feedback, corr.ref_opaca, d.id_nota, d.nota.id_sugerencia,
                                      d.nota.valoracion, d.nota.observacion)
                else:
                    ok = self._llamar(self.n.enviar_clasificacion, corr.ref_opaca, d.id_nota,
                                      [a.model_dump() for a in d.nota.articulos], d.nota.observacion)
            except NucleoNoDisponible:
                self.r.nucleo_caido = True
                return  # se conserva el orden: lo siguiente espera a la próxima pasada
            except ErrorNucleo as exc:
                self._fallo(id_caso, "nucleo_%s" % exc.codigo)
                return
            self.e.marcar_procesado(id_caso, d.tipo, d.id_nota, None if ok else "sin_solicitud")
            self.r.decisiones += 1
            telemetria.contador("conector_decision_enviada", tipo=d.tipo)


def ejecutar_pasada(veridy, nucleo, estado: est.Estado, id_empresa: str = "veridy",
                    ahora: Callable[[], float] = time.time) -> ResultadoPasada:
    dueno = str(uuid.uuid4())
    if not estado.tomar_cerrojo(CERROJO, dueno, ahora(), TTL_CERROJO_S):
        return ResultadoPasada(omitida=True, resultado="omitida")
    id_ejecucion = estado.iniciar_ejecucion()
    t0 = time.monotonic()
    r = ResultadoPasada()
    try:
        p = _Pasada(veridy, nucleo, estado, id_empresa, ahora)
        r = p.r
        casos = sorted(veridy.listar_casos(), key=lambda c: (str(c.get("creation_date") or ""), str(c.get("id"))))
        r.casos = len(casos)
        for meta in casos:
            try:
                p.procesar(meta)
            except Exception as exc:  # una falla en un caso no detiene la pasada
                r.errores += 1
                log.warning("falla inesperada en un caso: %s", type(exc).__name__)
        r.resultado = "ok" if r.exitosa else ("nucleo_caido" if r.nucleo_caido and not r.errores else "con_errores")
    except Exception as exc:
        r.errores += 1
        r.resultado = "error_" + type(exc).__name__
        log.error("la pasada falló: %s", type(exc).__name__)
    finally:
        estado.cerrar_ejecucion(id_ejecucion, r.resultado[:60], casos=r.casos, enviados=r.enviados,
                                publicadas=r.sugerencias, decisiones=r.decisiones, errores=r.errores)
        estado.soltar_cerrojo(CERROJO, dueno)
        telemetria.evento("conector_pasada", casos=r.casos, resultado=r.resultado,
                          duracion_ms=round((time.monotonic() - t0) * 1000))
    return r
