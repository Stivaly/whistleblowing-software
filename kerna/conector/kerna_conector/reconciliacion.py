"""Una pasada de reconciliación: pura y probable, con Veridy, núcleo y estado inyectados.

Privacidad: el texto del caso solo vive en variables locales de la pasada; no va a disco, a registros ni a
telemetría. El identificador real del caso solo llega al `estado`; al núcleo solo va la `ref_opaca`.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
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
MOTIVOS_REINTENTABLES = {"cadena_agotada", "tiempo_agotado"}


@dataclass
class ResultadoPasada:
    casos: int = 0
    enviados: int = 0
    reenviados: int = 0
    reprocesados: int = 0
    sugerencias: int = 0
    estados: int = 0
    decisiones: int = 0
    compartidos: int = 0
    errores: int = 0
    nucleo_caido: bool = False
    omitida: bool = False
    resultado: str = "ok"

    @property
    def exitosa(self) -> bool:
        return not (self.errores or self.nucleo_caido)


class _Pasada:
    def __init__(self, veridy, nucleo, estado: est.Estado, id_empresa: str, ahora: Callable[[], float],
                 compartir_con: str = "", reprocesar: bool = False, reintentos_max: int = 3,
                 reintento_horas: float = 24.0, envios_max: int = 5):
        self.envios_max, self.envios = envios_max, 0  # tope de envíos al núcleo por pasada (casos nuevos y reintentos)
        self.reprocesar = reprocesar
        self.reintentos_max, self.reintento_horas = reintentos_max, reintento_horas
        self.v, self.n, self.e, self.ahora = veridy, nucleo, estado, ahora
        self.compartir_con = compartir_con
        self.id_receptor: Optional[str] = None
        self.compartir_bloqueado = False
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

    def _cupo(self) -> bool:
        """Reserva un envío al núcleo en esta pasada; sin cupo el caso espera la siguiente (no consume intento)."""
        if self.envios_max > 0 and self.envios >= self.envios_max:
            return False
        self.envios += 1
        return True

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

    # ---- compartir acceso (opcional) ----------------------------------------------------------------------
    def compartir(self, meta: dict) -> None:
        """Da acceso al receptor `compartir_con` (operación grant de Veridy; la clave del caso se re-cifra en el
        servidor). Idempotente: se marca en el estado y se comprueba la lista de receptores del caso. Nunca
        registra contenido de la denuncia. Un fallo aquí no afecta al resto de la pasada."""
        if not self.compartir_con or self.compartir_bloqueado:
            return
        id_caso = str(meta["id"])
        if meta.get("accessible") is False:
            return
        try:
            if self.id_receptor is None:
                self.id_receptor = self.v.buscar_receptor(self.compartir_con)
                if self.id_receptor is None:
                    self.compartir_bloqueado = True
                    log.warning("compartir: no existe el receptor configurado")
                    return
            if self.id_receptor == self.id_cuenta:
                self.compartir_bloqueado = True
                return
            if self.e.objeto_procesado(id_caso, "compartido", self.id_receptor):
                return
            caso = self.v.leer_caso(id_caso)
            ya = any(r.get("id") == self.id_receptor and r.get("active", True) for r in (caso.get("receivers") or []))
            del caso
            if not ya:
                self.v.compartir_caso(id_caso, self.id_receptor)
                self.r.compartidos += 1
                telemetria.contador("conector_caso_compartido")
                telemetria.evento("conector_caso_compartido")
            self.e.marcar_procesado(id_caso, "compartido", self.id_receptor)
        except CasoNoAccesible as exc:
            if exc.codigo == 403:  # sin permiso can_grant_access_to_reports: no insistir en esta pasada
                self.compartir_bloqueado = True
            log.warning("compartir: Veridy rechazó la operación (http %s)", exc.codigo)
        except ErrorVeridy as exc:
            log.warning("compartir: error de Veridy (%s)", exc.codigo or "red")
        except Exception as exc:
            log.warning("compartir: falla inesperada (%s)", type(exc).__name__)

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
            if self.reintentos_max > 0:
                self._reproceso(corr)
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
        if not self._cupo():
            del relato
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

    # ---- reintento automático de revision_manual por fallo de modelos ---------------------------------------
    @staticmethod
    def _ref_reproceso(ref_opaca: str, k: int = 1) -> str:
        """Referencia derivada y estable por ronda: el núcleo la ve como un caso nuevo y repetirla es seguro."""
        return str(uuid.uuid5(uuid.NAMESPACE_OID, "%s/reproceso%d" % (ref_opaca, k)))

    @staticmethod
    def _epoch(iso: Optional[str]) -> float:
        try:
            return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    def _reproceso(self, corr: est.Correspondencia) -> None:
        """Reintenta (hasta `reintentos_max`, uno cada `reintento_horas`) los casos cuya última sugerencia es
        `revision_manual` por fallo de modelos. Cada ronda k usa una ref_opaca derivada; al completar se publica
        una nota nueva (el cliente muestra la más reciente). El estado guarda intentos y fecha en `objeto_procesado`
        (`enviado<k>` con su fecha, `resuelto<k>`, `final`). `reprocesar` salta la espera de la 1.ª ronda."""
        id_caso, e = corr.id_caso, self.e
        if e.objeto_procesado(id_caso, "reproceso", "final"):
            return
        k = sum(1 for i in range(1, self.reintentos_max + 1) if e.objeto_procesado(id_caso, "reproceso", "enviado%d" % i))
        en_vuelo = k > 0 and not e.objeto_procesado(id_caso, "reproceso", "resuelto%d" % k)
        espera = self.reintento_horas * 3600
        if not en_vuelo:
            if k >= self.reintentos_max:
                e.marcar_procesado(id_caso, "reproceso", "final")
                return
            if k > 0 and self.ahora() - float(e.id_nota_procesado(id_caso, "reproceso", "ts%d" % k) or 0) < espera:
                return
        caso = self._leer(id_caso)
        if caso is None:
            return
        if not en_vuelo:
            propias = lector_casos.notas_de_cuenta(caso, self.id_cuenta, "kerna_sugerencia")
            ultima = max(propias, key=lambda n: n.nota.generado_en, default=None)
            if ultima is None or ultima.nota.estado != "revision_manual" or \
                    ultima.nota.motivo_revision not in MOTIVOS_REINTENTABLES:
                e.marcar_procesado(id_caso, "reproceso", "final")
                return
            if k == 0 and not self.reprocesar and self.ahora() - self._epoch(ultima.nota.generado_en) < espera:
                return
            try:
                relato = lector_casos.extraer_relato(caso)
            except Exception as exc:
                self._fallo(id_caso, "ilegible_" + type(exc).__name__)
                return
            if not relato.strip():
                self._fallo(id_caso, "sin_texto")
                return
            if not self._cupo():
                del relato
                return
            texto = anonimizar(relato).texto[:MAX_TEXTO]
            del relato
            ref = self._ref_reproceso(corr.ref_opaca, k + 1)
            try:
                self._llamar(self.n.enviar_caso, ref, texto)
            except NucleoNoDisponible:
                self.r.nucleo_caido = True
                return
            except ErrorNucleo as exc:
                self._fallo(id_caso, "nucleo_%s" % exc.codigo)
                return
            finally:
                del texto
            e.marcar_procesado(id_caso, "reproceso", "ts%d" % (k + 1), str(self.ahora()))
            e.marcar_procesado(id_caso, "reproceso", "enviado%d" % (k + 1), ref)
            self.r.reenviados += 1
            telemetria.contador("conector_caso_reenviado", intento=k + 1)
            telemetria.evento("conector_reintento", ref_opaca=corr.ref_opaca, intento=k + 1,
                              motivo=str(ultima.nota.motivo_revision) if not en_vuelo else None)
            log.info("reintento %d/%d enviado", k + 1, self.reintentos_max)
            return
        try:
            res = self._llamar(self.n.consultar_sugerencia, self._ref_reproceso(corr.ref_opaca, k))
        except NucleoNoDisponible:
            self.r.nucleo_caido = True
            return
        except ErrorNucleo as exc:
            self._fallo(id_caso, "nucleo_%s" % exc.codigo)
            return
        if res is None or res.get("estado") not in ("completada", "revision_manual"):
            return
        e.marcar_procesado(id_caso, "reproceso", "resuelto%d" % k)
        if res.get("estado") == "revision_manual" and res.get("motivo_revision") in MOTIVOS_REINTENTABLES:
            log.info("reintento %d/%d: sigue en revision_manual", k, self.reintentos_max)
            if k >= self.reintentos_max:
                e.marcar_procesado(id_caso, "reproceso", "final")
            return
        id_nota = self.v.publicar_nota(id_caso, publicador.contenido(publicador.armar_sugerencia(res))).get("id")
        e.marcar_procesado(id_caso, "reproceso", "final", str(id_nota or ""))
        self.r.reprocesados += 1
        log.info("reintento %d: nueva sugerencia estado=%s modo=%s", k, res.get("estado"), res.get("modo"))
        telemetria.contador("conector_caso_reprocesado", estado=str(res.get("estado")), modo=str(res.get("modo")))
        telemetria.evento("conector_reproceso", ref_opaca=corr.ref_opaca, intento=k, estado=str(res.get("estado")),
                          modo=str(res.get("modo")))

    @staticmethod
    def _valoracion(d) -> str:
        """util / no_util (feedback) o ninguno_aplica (clasificación sin artículos); nunca texto libre."""
        if d.tipo == "feedback":
            return "util" if str(d.nota.valoracion) == "arriba" else "no_util"
        return "clasificado" if d.nota.articulos else "ninguno_aplica"

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
            telemetria.evento("conector_valoracion", ref_opaca=corr.ref_opaca, tipo=d.tipo,
                              valoracion=self._valoracion(d))


def ejecutar_pasada(veridy, nucleo, estado: est.Estado, id_empresa: str = "veridy",
                    ahora: Callable[[], float] = time.time, compartir_con: str = "",
                    reprocesar: bool = False, reintentos_max: int = 3,
                    reintento_horas: float = 24.0, envios_max: int = 5) -> ResultadoPasada:
    dueno = str(uuid.uuid4())
    if not estado.tomar_cerrojo(CERROJO, dueno, ahora(), TTL_CERROJO_S):
        return ResultadoPasada(omitida=True, resultado="omitida")
    id_ejecucion = estado.iniciar_ejecucion()
    t0 = time.monotonic()
    r = ResultadoPasada()
    try:
        p = _Pasada(veridy, nucleo, estado, id_empresa, ahora, compartir_con, reprocesar, reintentos_max, reintento_horas,
                    envios_max)
        r = p.r
        casos = sorted(veridy.listar_casos(), key=lambda c: (str(c.get("creation_date") or ""), str(c.get("id"))))
        r.casos = len(casos)
        for meta in casos:
            p.compartir(meta)
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
