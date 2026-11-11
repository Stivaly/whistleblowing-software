"""Cadena por caso, en orden fijo: anonimización, clasificación, recuperación, generación, validación, registro."""
from __future__ import annotations

import asyncio

import logging
import uuid
from datetime import datetime, timezone

from kerna_comun import anonimizador, telemetria

from . import prompts
from .enrutador import CadenaAgotada, Enrutador, PlazoAgotado
from .retriever import RecuperacionFallida, Retriever
from .validador import validar

_log = logging.getLogger("kerna.nucleo")


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validar_clasificacion(d) -> dict:
    if not isinstance(d, dict) or not isinstance(d.get("materia"), str) or d.get("riesgo") not in prompts.RIESGOS:
        raise ValueError("clasificación inválida")
    return {"materia": d["materia"][:40], "riesgo": d["riesgo"]}


def _validar_generacion(d) -> list:
    if not isinstance(d, dict) or not isinstance(d.get("articulos"), list):
        raise ValueError("generación inválida")
    return d["articulos"]


def _articulo(f: dict) -> str:
    return str(f.get("articulo") or "")


def _norma(f: dict) -> str:
    return str(f.get("norma") or f.get("tipo_numero") or "")


class Orquestador:
    def __init__(self, config, almacen, enrutador: Enrutador, retriever: Retriever, reloj):
        self.config, self.almacen, self.enrutador, self.retriever, self.reloj = config, almacen, enrutador, retriever, reloj
        # Cadenas simultáneas: el resto espera su turno (los proveedores limitan las peticiones por minuto).
        self._turnos = asyncio.Semaphore(max(1, int(getattr(config, "concurrencia", 2))))

    async def procesar(self, solicitud: dict, texto: str) -> None:
        """Ejecuta la cadena y deja el resultado en el almacén. Nunca propaga errores ni registra el texto."""
        async with self._turnos:  # la espera del turno no cuenta para el plazo global
            await self._procesar(solicitud, texto)

    async def _procesar(self, solicitud: dict, texto: str) -> None:
        cliente, ref, ids = solicitud["cliente"], solicitud["ref_opaca"], solicitud["id_solicitud"]
        inicio = self.reloj()
        reg: dict = {"tokens_entrada": 0, "tokens_salida": 0, "citas_rechazadas": 0}
        try:
            resultado = await self._cadena(ids, texto, inicio, reg)
        except PlazoAgotado:
            resultado = self._manual("tiempo_agotado")
        except (CadenaAgotada, RecuperacionFallida):
            resultado = self._manual("cadena_agotada")
        except Exception as e:  # defecto inesperado: nunca se registra el contenido
            _log.error("error inesperado en la cadena: %s", type(e).__name__)
            resultado = self._manual("cadena_agotada")
        finally:
            texto = ""  # el texto del caso no sobrevive a la solicitud
        articulos = resultado.pop("articulos", [])
        resultado.setdefault("recuperacion", reg.get("recuperacion", "nube"))
        resultado.setdefault("version_corpus", reg.get("version_corpus", 0))
        contingencia = resultado["modo"] != "oficial" or resultado["recuperacion"] == "local"
        campos = {**reg, **resultado, "contingencia": contingencia, "generado_en": iso(self.reloj()),
                  "finalizada_en": self.reloj(), "duracion_ms": round((self.reloj() - inicio) * 1000)}
        if articulos:
            await self.almacen.guardar_articulos(ids, articulos)
        await self.almacen.actualizar_solicitud(cliente, ref, campos, solo_si_pendiente=True)
        telemetria.evento("solicitud_terminada", id_solicitud=ids, cliente=cliente, estado=resultado["estado"],
                          motivo=resultado.get("motivo_revision"), modo=resultado["modo"],
                          recuperacion=resultado["recuperacion"], contingencia=contingencia,
                          articulos=len(articulos), citas_rechazadas=reg["citas_rechazadas"],
                          tokens_entrada=reg["tokens_entrada"], tokens_salida=reg["tokens_salida"],
                          duracion_ms=round((self.reloj() - inicio) * 1000))

    @staticmethod
    def _manual(motivo: str, **extra) -> dict:
        return {"estado": "revision_manual", "motivo_revision": motivo, "modo": "manual", "articulos": [], **extra}

    async def _cadena(self, ids: str, texto: str, inicio: float, reg: dict) -> dict:
        base = {"id_solicitud": ids}
        # 1. segunda anonimización
        with telemetria.etapa("anonimizacion", **base):
            limpio = anonimizador.anonimizar(texto).texto
        # 2. clasificación previa (nivel de menor costo y su respaldo); si falla, sigue con valores neutros
        clasif = {"materia": "otro", "riesgo": "medio"}
        with telemetria.etapa("clasificacion", **base) as a:
            try:
                r = await self.enrutador.generar(prompts.SISTEMA_CLASIFICADOR, prompts.usuario_clasificador(limpio),
                                                 prompts.ESQUEMA_CLASIFICACION, _validar_clasificacion, inicio,
                                                 desde_modelo=self.config.modelo_clasificador)
                clasif = r.datos
                self._sumar(reg, r)
                a.update(modo=r.modo, proveedor=r.proveedor, modelo=r.modelo, tokens_entrada=r.tokens_entrada,
                         tokens_salida=r.tokens_salida)
            except (CadenaAgotada,):
                a["motivo"] = "cadena_agotada"
        reg["materia"], reg["riesgo"] = clasif["materia"], clasif["riesgo"]
        # 3. recuperación
        with telemetria.etapa("recuperacion", **base) as a:
            rec = await self.retriever.recuperar(limpio)
            a.update(recuperacion=rec.recuperacion, embedding=rec.embedding, coleccion=rec.coleccion,
                     version_corpus=rec.version_corpus, fragmentos=len(rec.fragmentos), tokens_entrada=rec.tokens_embedding)
        reg.update(recuperacion=rec.recuperacion, embedding=rec.embedding, coleccion=rec.coleccion,
                   version_corpus=rec.version_corpus, version_indice=str(rec.version_corpus))
        reg["tokens_entrada"] += rec.tokens_embedding
        parcial = {"recuperacion": rec.recuperacion, "version_corpus": rec.version_corpus}
        if not rec.fragmentos or rec.mejor_puntaje < self.retriever.umbral:
            return {"estado": "revision_manual", "motivo_revision": "sin_normativa_aplicable",
                    "modo": "manual", "articulos": [], **parcial}
        # 4. generación
        fragmentos = rec.fragmentos[: self.config.top_k]
        with telemetria.etapa("generacion", **base) as a:
            gen = await self.enrutador.generar(prompts.SISTEMA_GENERADOR,
                                               prompts.usuario_generador(limpio, fragmentos, clasif["materia"], clasif["riesgo"]),
                                               prompts.ESQUEMA_GENERACION, _validar_generacion, inicio)
            a.update(modo=gen.modo, proveedor=gen.proveedor, modelo=gen.modelo, tokens_entrada=gen.tokens_entrada,
                     tokens_salida=gen.tokens_salida, json_valido=True)
        self._sumar(reg, gen)
        reg.update(modo_generacion=gen.modo, proveedor=gen.proveedor, modelo=gen.modelo)
        parcial["modo"] = gen.modo
        # 5. validación de citas
        with telemetria.etapa("validacion", **base) as a:
            aceptados, rechazados = validar(gen.datos, fragmentos, self.config.max_articulos)
            a.update(articulos=len(aceptados), citas_rechazadas=len(rechazados))
        reg["citas_rechazadas"] = len(rechazados)
        reg["motivos_rechazo"] = sorted({r["motivo"] for r in rechazados})
        if not aceptados:
            return {"estado": "revision_manual", "motivo_revision": "validacion_fallida", "articulos": [], **parcial}
        # 6. registro por artículo
        articulos = []
        for ac in aceptados:
            f = ac["fragmento"]
            articulos.append({"id_sugerencia": str(uuid.uuid4()), "id_articulo": f["fragmento_id"], "norma": _norma(f),
                              "articulo": _articulo(f), "explicacion": ac["explicacion"], "cita": ac["cita"],
                              "enlace_fuente": str(f.get("url_fuente") or ""), "confianza": ac["confianza"]})
        return {"estado": "completada", "motivo_revision": None, "articulos": articulos, **parcial}

    @staticmethod
    def _sumar(reg: dict, r) -> None:
        reg["tokens_entrada"] += r.tokens_entrada
        reg["tokens_salida"] += r.tokens_salida
