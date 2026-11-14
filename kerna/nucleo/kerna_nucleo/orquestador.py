"""Cadena por caso, en orden fijo: anonimización, clasificación, recuperación, generación, validación, registro."""
from __future__ import annotations

import asyncio
import contextvars
import logging
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from kerna_comun import anonimizador, telemetria

from . import prompts
from .evaluador import Evaluador
from .evaluador_ids import EvaluadorIds, segmentar_articulo
from .reranker_llm import RerankerLLM
from .revisor import Revisor
from .enrutador import CadenaAgotada, Enrutador, PlazoAgotado
from .retriever import RecuperacionFallida, Retriever
from .validador import normalizar, validar

_log = logging.getLogger("kerna.nucleo")
# Orden completo que dejó el evaluador en la cadena en curso (para el reranker LLM y la sonda de evaluación).
_ORDEN_EVAL: contextvars.ContextVar = contextvars.ContextVar("orden_evaluador", default=None)
_SIN_REVISION = SimpleNamespace(dictamenes={}, alertas=[])  # revisor activo sin dictámenes: todo «sin_revision»


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
            for a in articulos:  # solo el nombre público de la norma, para el tablero del front
                telemetria.evento("articulo_sugerido", id_solicitud=ids, norma=str(a.get("norma", "")))
        await self.almacen.actualizar_solicitud(cliente, ref, campos, solo_si_pendiente=True)
        telemetria.evento("solicitud_terminada", id_solicitud=ids, cliente=cliente, estado=resultado["estado"],
                          motivo=resultado.get("motivo_revision"), modo=resultado["modo"],
                          recuperacion=resultado["recuperacion"], contingencia=contingencia,
                          modelo=reg.get("modelo"), proveedor=reg.get("proveedor"), articulos=len(articulos), citas_rechazadas=reg["citas_rechazadas"],
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
        # 3. recuperación (KERNA_MULTIQUERY: antes se extrae el perfil, que el evaluador reutiliza)
        perfil = await self._perfil_previo(limpio, inicio, reg, base)
        consultas = (perfil.conductas[: self.config.multiquery_max] if perfil else [])
        with telemetria.etapa("recuperacion", **base) as a:
            rec = await (self.retriever.recuperar(limpio, consultas=consultas) if consultas
                         else self.retriever.recuperar(limpio))
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
        _ORDEN_EVAL.set(None)
        if getattr(self.config, "evaluador", False) and len(rec.fragmentos) > 1:
            fragmentos = await self._evaluar(limpio, rec.fragmentos, inicio, reg, base, perfil)
        if getattr(self.config, "rerank_llm", False) and len(rec.fragmentos) > 1:
            fragmentos = await self._rerank_llm(limpio, rec.fragmentos, fragmentos, inicio, reg, base)
        self._sonda("orden", [(f["fragmento_id"], f.get("puntaje_evaluador"), bool(f.get("rerank_llm"))) for f in fragmentos])
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
            self._sonda("generador", {"ids": [str(d.get("fragmento_id")) for d in gen.datos if isinstance(d, dict)],
                                      "rechazos": [(r["fragmento_id"], r["motivo"]) for r in rechazados]})
            if getattr(self.config, "generador_completar", 0) > 0:
                aceptados = self._completar(aceptados, fragmentos)
            a.update(articulos=len(aceptados), citas_rechazadas=len(rechazados))
        reg["citas_rechazadas"] = len(rechazados)
        reg["motivos_rechazo"] = sorted({r["motivo"] for r in rechazados})
        if not aceptados:
            return {"estado": "revision_manual", "motivo_revision": "validacion_fallida", "articulos": [], **parcial}
        # 5b. revisión jurídica (KERNA_REVISOR): anota cada artículo ya validado; nunca elimina ni bloquea
        rev = await self._revisar(limpio, aceptados, inicio, reg, base, perfil) if getattr(self.config, "revisor", False) else None
        # 6. registro por artículo
        articulos = []
        for ac in aceptados:
            f = ac["fragmento"]
            articulos.append({"id_sugerencia": str(uuid.uuid4()), "id_articulo": f["fragmento_id"], "norma": _norma(f),
                              "articulo": _articulo(f), "explicacion": ac["explicacion"], "cita": ac["cita"],
                              "enlace_fuente": str(f.get("url_fuente") or ""), "confianza": ac["confianza"]})
            if rev is not None:
                articulos[-1].update(self._anotacion(rev, f["fragmento_id"]))
        return {"estado": "completada", "motivo_revision": None, "articulos": articulos, **parcial}

    def _sonda(self, nombre: str, datos) -> None:
        """Gancho opcional de las mediciones (solo IDs y puntajes, nunca texto): `orq.sonda = f(nombre, datos)`."""
        f = getattr(self, "sonda", None)
        if f is not None:
            f(nombre, datos)

    def _completar(self, aceptados: list, fragmentos: list) -> list:
        """KERNA_GENERADOR_COMPLETAR=N: el resultado sigue el orden del evaluador (o del reranker) y no pierde sus N
        primeros artículos por una omisión del generador: el que el generador omitió, o cuya cita no validó, entra con
        una frase del propio artículo que el evaluador indicó (o el comienzo del texto) y confianza baja."""
        n = self.config.generador_completar
        por_id = {a["fragmento"]["fragmento_id"]: a for a in aceptados}
        minimo = getattr(self.config, "generador_min_puntaje", 1)
        out = []
        for pos, f in enumerate(fragmentos):
            if len(out) >= self.config.max_articulos:
                break
            a = por_id.get(f["fragmento_id"])
            if a is not None:
                out.append(a)
                continue
            if pos >= n:
                continue
            puntaje = f.get("puntaje_evaluador")
            if not (f.get("rerank_llm") or (isinstance(puntaje, (int, float)) and puntaje >= minimo)):
                continue
            texto = f.get("texto") or ""
            segs = segmentar_articulo(texto)
            cita = ""
            for fid in f.get("frase_ids_evaluador") or []:
                try:
                    j = int(str(fid).split(".")[1])
                    cita = segs[j - 1]
                except (IndexError, ValueError):
                    continue
                break
            if len(normalizar(cita)) < 10 or normalizar(cita) not in normalizar(texto):
                cita = " ".join(texto.split())[:240]
            if len(normalizar(cita)) < 10:
                continue
            conf = max(0.1, (puntaje or 1) / 3 * 0.6) if isinstance(puntaje, (int, float)) else 0.3
            out.append({"fragmento": f, "cita": cita.strip(), "confianza": round(conf, 2),
                        "explicacion": "Los hechos descritos podrían relacionarse con este artículo, según el análisis "
                                       "previo de aplicabilidad."})
        return out[: self.config.max_articulos]

    async def _rerank_llm(self, limpio: str, retriever: list, evaluados: list, inicio: float, reg: dict, base: dict) -> list:
        """KERNA_RERANK_LLM: reordena la ventana (por defecto, el orden completo del evaluador) con el reranker listwise
        y entrega los top_k. Cualquier falla conserva el orden recibido; solo el plazo global se propaga."""
        c = self.config
        orden_eval = _ORDEN_EVAL.get()
        ids_eval = [f["fragmento_id"] for f in orden_eval] if orden_eval else []
        ventana = (orden_eval if (c.rerank_llm_fuente == "evaluador" and orden_eval) else retriever)
        with telemetria.etapa("rerank_llm", **base) as a:
            r = await RerankerLLM(self.enrutador.generar, c.rerank_llm_ventana, c.rerank_llm_voto_eval).reordenar(
                limpio, list(ventana), inicio, ids_eval)
            a.update(usado=r.usado, motivo=r.motivo, permutaciones=r.permutaciones, descartados_id=r.descartados_id,
                     tokens_entrada=r.tokens_entrada, tokens_salida=r.tokens_salida)
        reg["tokens_entrada"] += r.tokens_entrada
        reg["tokens_salida"] += r.tokens_salida
        if not r.usado:
            return evaluados
        if orden_eval:                       # conservar puntajes y frases del evaluador en los fragmentos reordenados
            ev = {f["fragmento_id"]: f for f in orden_eval}
            r.fragmentos = [dict(ev.get(f["fragmento_id"], {}), **f) for f in r.fragmentos]
        return r.fragmentos[: max(c.top_k, 1)]

    def _evaluador(self):
        clase = EvaluadorIds if str(self.config.evaluador_variante).startswith("3") else Evaluador
        return clase(self.enrutador.generar, variante=self.config.evaluador_variante, salida=self.config.top_k)

    async def _perfil_previo(self, limpio: str, inicio: float, reg: dict, base: dict):
        """Con KERNA_MULTIQUERY (y evaluador por IDs con perfil), extrae el perfil de la denuncia antes de recuperar.
        El evaluador lo reutiliza: la extracción se paga una sola vez. Una falla deja la recuperación sin consultas extra."""
        c = self.config
        if not (getattr(c, "multiquery", False) and getattr(c, "evaluador", False)
                and str(c.evaluador_variante).startswith("3")):
            return None
        ev = self._evaluador()
        if not getattr(ev, "usa_perfil", False):
            return None
        with telemetria.etapa("perfil", **base) as a:
            p = await ev.extraer_perfil(limpio, inicio)
            a.update(ok=p.ok, conductas=len(p.conductas), tokens_entrada=p.tokens_entrada, tokens_salida=p.tokens_salida)
        reg["tokens_entrada"] += p.tokens_entrada
        reg["tokens_salida"] += p.tokens_salida
        return p

    async def _evaluar(self, limpio: str, candidatos: list, inicio: float, reg: dict, base: dict, perfil=None) -> list:
        """Agente evaluador (KERNA_EVALUADOR): reordena los candidatos y entrega los top_k al agente final.
        Cualquier falla conserva el orden del retriever; solo el plazo global se propaga."""
        n = max(self.config.evaluador_candidatos, self.config.top_k)
        ev = self._evaluador()
        with telemetria.etapa("evaluacion", **base) as a:
            r = await (ev.evaluar(limpio, candidatos[:n], inicio, perfil=perfil) if perfil is not None
                       else ev.evaluar(limpio, candidatos[:n], inicio))
            a.update(usado=r.usado, motivo=r.motivo, aplican=r.aplican, descartados_id=r.descartados_id,
                     descartados_cita=r.descartados_cita, tokens_entrada=r.tokens_entrada,
                     tokens_salida=r.tokens_salida)
        reg["tokens_entrada"] += r.tokens_entrada
        reg["tokens_salida"] += r.tokens_salida
        _ORDEN_EVAL.set(getattr(r, "orden", None) or None)
        self._sonda("evaluador_orden", [(f["fragmento_id"], f.get("puntaje_evaluador")) for f in (getattr(r, "orden", None) or [])])
        return r.fragmentos

    async def _revisar(self, limpio: str, aceptados: list, inicio: float, reg: dict, base: dict, perfil=None):
        """Agente revisor (KERNA_REVISOR), después de la validación: ve solo los artículos ya validados (con su texto
        íntegro, que la validación ya comprobó) y las leyes de esos artículos. Falla segura: ante cualquier falla, o si
        se agota el plazo, las sugerencias salen sin cambios, marcadas «sin_revision»."""
        items = [{"fragmento": ac["fragmento"], "confianza": ac["confianza"]} for ac in aceptados]
        with telemetria.etapa("revision", **base) as a:
            try:
                r = await Revisor(self.enrutador.generar, getattr(self.config, "revisor_sin_causales", ())).revisar(limpio, items, inicio,
                                                                 perfil=getattr(perfil, "texto", "") or "")
            except PlazoAgotado:
                r = None
                a["motivo"] = "plazo_agotado"
            except Exception as e:  # defecto inesperado: nunca se registra el contenido
                _log.error("error inesperado en el revisor: %s", type(e).__name__)
                r = None
                a["motivo"] = "revisor_fallido"
            if r is not None:
                a.update(usado=r.usado, motivo=r.motivo, familias=r.familias, confirmados=r.confirmados,
                         condicionados=r.condicionados, vetados=r.vetados, vetos_degradados=r.vetos_degradados,
                         descartados_id=r.descartados_id, alertas=len(r.alertas), tokens_entrada=r.tokens_entrada,
                         tokens_salida=r.tokens_salida)
                reg["tokens_entrada"] += r.tokens_entrada
                reg["tokens_salida"] += r.tokens_salida
        usado = bool(r is not None and r.usado)
        reg["revision_juridica"] = "revisado" if usado else "sin_revision"
        reg["alertas_revision"] = list(r.alertas) if usado else []
        return r if usado else _SIN_REVISION

    @staticmethod
    def _anotacion(rev, fragmento_id: str) -> dict:
        """Campos del artículo según el dictamen; sin dictamen (falla o artículo omitido) queda «sin_revision»."""
        d = rev.dictamenes.get(fragmento_id)
        if d is None:
            return {"revision_juridica": "sin_revision"}
        return {"revision_juridica": "revisado", "dictamen": d["dictamen"], "causal_veto": d["causal_veto"],
                "condiciones": d["condiciones"], "alertas_revision": rev.alertas, "hecho_ids_revision": d["hecho_ids"],
                "frase_ids_revision": d["frase_ids"], "confianza_revisor": d["confianza_ajustada"]}

    @staticmethod
    def _sumar(reg: dict, r) -> None:
        reg["tokens_entrada"] += r.tokens_entrada
        reg["tokens_salida"] += r.tokens_salida
