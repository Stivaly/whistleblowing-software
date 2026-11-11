"""Enrutador de modelos (IGeneracion): cadena de niveles con reintentos, cortocircuito y plazo global."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from kerna_comun import telemetria

from .proveedores import ErrorProveedor


class PlazoAgotado(Exception):
    """Se superó el plazo global de la solicitud."""


class CadenaAgotada(Exception):
    """Fallaron todos los niveles disponibles."""


@dataclass
class Nivel:
    modo: str
    proveedor: str
    modelo: str
    esquema: bool = True
    sistema: bool = True

    @classmethod
    def desde_dict(cls, d: dict) -> "Nivel":
        return cls(d["modo"], d.get("proveedor", "gemini"), d["modelo"], d.get("esquema", True), d.get("sistema", True))


@dataclass
class Resultado:
    datos: Any
    modo: str
    proveedor: str
    modelo: str
    tokens_entrada: int = 0
    tokens_salida: int = 0
    intentos: int = 0


@dataclass
class _Estado:
    fallas: list = field(default_factory=list)
    excluido_hasta: float | None = None


def extraer_json(texto: str) -> Any:
    """Parsea JSON de una salida de modelo; tolera cercos ``` y texto alrededor. ValueError si no hay JSON."""
    t = (texto or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    try:
        return json.loads(t)
    except ValueError:
        pass
    ini, fin = t.find("{"), t.rfind("}")
    if ini >= 0 and fin > ini:
        return json.loads(t[ini:fin + 1])
    raise ValueError("sin JSON")


class Enrutador:
    def __init__(self, niveles: list[Nivel], gemini, reloj=time.time, dormir=None, plazo_llamada=None,
                 plazo_global=240.0, corte=30.0, esperas=(1.0, 2.0, 4.0), umbral_fallas=3, ventana=300.0,
                 exclusion=600.0):
        self.niveles = niveles
        self._gemini = gemini
        self._reloj = reloj
        self._dormir = dormir or asyncio.sleep
        self._plazo = plazo_llamada or (lambda aw, s: asyncio.wait_for(aw, s))
        self.plazo_global = plazo_global
        self.corte = corte
        self.esperas = tuple(esperas)
        self._umbral = umbral_fallas
        self._ventana = ventana
        self._exclusion = exclusion
        self._estado: dict[str, _Estado] = {}

    # ---- cortocircuito
    def _e(self, nivel: Nivel) -> _Estado:
        return self._estado.setdefault(nivel.modelo, _Estado())

    def _registrar_falla(self, nivel: Nivel) -> None:
        e, ahora = self._e(nivel), self._reloj()
        e.fallas = [t for t in e.fallas if ahora - t < self._ventana] + [ahora]
        if len(e.fallas) >= self._umbral and e.excluido_hasta is None:
            e.excluido_hasta = ahora + self._exclusion
            telemetria.evento("cortocircuito_abierto", proveedor=nivel.proveedor, modelo=nivel.modelo)

    def _registrar_exito(self, nivel: Nivel) -> None:
        e = self._e(nivel)
        e.fallas, e.excluido_hasta = [], None

    def excluido(self, nivel: Nivel) -> bool:
        e = self._estado.get(nivel.modelo)
        return bool(e and e.excluido_hasta is not None)

    async def _disponible(self, nivel: Nivel) -> bool:
        e = self._e(nivel)
        if e.excluido_hasta is None:
            return True
        if self._reloj() < e.excluido_hasta:
            return False
        try:
            sano = await self._plazo(self._gemini.salud(nivel.modelo), self.corte)
        except Exception:
            sano = False
        if sano:
            self._registrar_exito(nivel)
            telemetria.evento("cortocircuito_cerrado", proveedor=nivel.proveedor, modelo=nivel.modelo)
            return True
        e.excluido_hasta = self._reloj() + self._exclusion
        return False

    # ---- generación
    def _restante(self, inicio: float) -> float:
        return self.plazo_global - (self._reloj() - inicio)

    async def _llamar(self, nivel: Nivel, sistema, usuario, esquema, restante: float):
        aw = self._gemini.generar(nivel.modelo, sistema, usuario, esquema if nivel.esquema else None,
                                  con_sistema=nivel.sistema, degradar=True)
        return await self._plazo(aw, min(self.corte, restante))

    async def generar(self, sistema: str, usuario: str, esquema: dict | None, validar: Callable[[Any], Any],
                      inicio: float, desde_modelo: str | None = None) -> Resultado:
        """Recorre los niveles en orden. `validar` recibe el JSON ya parseado y lanza ValueError si no sirve;
        una salida inválida cuenta como falla del nivel (sin reintento). `desde_modelo` recorta la cadena."""
        niveles = self.niveles
        if desde_modelo:
            niveles = [n for i, n in enumerate(self.niveles) if i >= next(
                (j for j, m in enumerate(self.niveles) if m.modelo == desde_modelo), 0)]
        for nivel in niveles:
            if self._restante(inicio) <= 0:
                raise PlazoAgotado()
            if not await self._disponible(nivel):
                continue
            n_esperas = len(self.esperas)
            for intento in range(n_esperas + 1):
                restante = self._restante(inicio)
                if restante <= 0:
                    raise PlazoAgotado()
                try:
                    r = await self._llamar(nivel, sistema, usuario, esquema, restante)
                    datos = validar(extraer_json(r.texto))
                except (asyncio.TimeoutError, TimeoutError):
                    err = ErrorProveedor(nivel.proveedor, None, True, "timeout")
                except ErrorProveedor as e:
                    err = e
                except ValueError:
                    self._registrar_falla(nivel)
                    telemetria.evento("nivel_fallido", modo=nivel.modo, modelo=nivel.modelo, codigo="json_invalido",
                                      intento=intento + 1, json_valido=False)
                    break
                else:
                    self._registrar_exito(nivel)
                    return Resultado(datos, nivel.modo, nivel.proveedor, nivel.modelo, r.tokens_entrada,
                                     r.tokens_salida, intento + 1)
                self._registrar_falla(nivel)
                telemetria.evento("nivel_fallido", modo=nivel.modo, modelo=nivel.modelo,
                                  codigo=str(err.codigo or "silencio"), intento=intento + 1)
                if not err.reintentable or intento >= n_esperas:
                    break
                espera = self.esperas[intento]
                if self._restante(inicio) <= espera:
                    raise PlazoAgotado()
                await self._dormir(espera)
        if self._restante(inicio) <= 0:
            raise PlazoAgotado()
        raise CadenaAgotada()
