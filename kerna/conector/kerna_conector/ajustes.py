"""Ajustes del panel que aplica el conector, leídos de la tabla `ajustes` (fila kerna/actual) en cada pasada.

Aplica: casos por ronda (`envios`), reintentos automáticos (`reintentos`), espera entre reintentos (`espera`, horas),
frecuencia de revisión de Veridy (`revision`, segundos) y «reintentar los de revisión manual» (`reprocesar`: una vez
por cada guardado), «compartir con» (`compartir`, equipos que reciben cada caso) y «avisar sin sugerencia tras»
(`alerta`, horas). Los de IA (revisor, artículos por caso, orden de modelos) son del núcleo. Un valor ausente o fuera
de rango se ignora y rige el valor del entorno. Sin tabla o con la tabla caída rigen los valores del entorno.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, replace
from typing import Any, Optional

from kerna_comun import ajustes_esquema as esq

from .config import Config
from .solicitudes import tabla_desde_entorno

log = logging.getLogger("kerna.conector")
PK, RK = "kerna", "actual"
APLICADOS = ("envios", "reintentos", "espera", "revision", "reprocesar", "compartir", "alerta")


@dataclass(frozen=True)
class Parametros:
    envios_max: int
    reintentos_max: int
    reintento_horas: float
    intervalo_s: float
    reprocesar_marca: Optional[str] = None  # `actualizado_en` del guardado que pidió reprocesar (None = no pidió)
    de_ajustes: bool = False                # True si los valores salen de la tabla
    alerta_h: int = 6                       # horas sin sugerencia para destacar un caso en el panel
    equipos: Optional[tuple[str, ...]] = None  # ids de equipo con quienes compartir (None = sin valor en la tabla: rige el entorno)


def _entero(x: Any, minimo: int, maximo: int) -> Optional[int]:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != int(x):
        return None
    return int(x) if minimo <= x <= maximo else None


def nombres_receptores(ids, entorno: Optional[dict] = None) -> tuple[str, ...]:
    """Nombres de cuenta receptora de Veridy de los equipos `ids`; `KERNA_EQUIPOS_RECEPTOR` (JSON {id: nombre}) los puede anular."""
    if entorno is None:
        entorno = os.environ
    try:
        anula = json.loads(entorno.get("KERNA_EQUIPOS_RECEPTOR") or "{}")
        anula = anula if isinstance(anula, dict) else {}
    except (TypeError, ValueError):
        anula = {}
    out: list[str] = []
    for i in ids or ():
        if i not in esq.EQUIPOS:
            continue
        n = str(anula.get(i) or esq.EQUIPOS[i]["receptor"]).strip()
        if n and n not in out:
            out.append(n)
    return tuple(out)


def parametros(cfg: Config, fila: Optional[dict]) -> Parametros:
    base = Parametros(cfg.envios_por_pasada, cfg.reintentos_max, cfg.reintento_horas, cfg.intervalo_s)
    if not fila:
        return base
    try:
        v = json.loads(fila.get("valores") or "{}")
    except (TypeError, ValueError):
        return base
    if not isinstance(v, dict):
        return base
    envios, reint = _entero(v.get("envios"), 1, 10), _entero(v.get("reintentos"), 0, 5)
    espera, rev = _entero(v.get("espera"), 1, 168), _entero(v.get("revision"), 5, 3600)
    alerta = v.get("alerta")
    alerta = alerta if not isinstance(alerta, bool) and alerta in (1, 6, 24) else base.alerta_h
    comp = v.get("compartir")
    equipos = tuple(dict.fromkeys(e for e in comp if isinstance(e, str) and e in esq.EQUIPOS)) if isinstance(comp, list) else None
    return replace(base, de_ajustes=True, alerta_h=int(alerta), equipos=equipos,
                   envios_max=envios if envios is not None else base.envios_max,
                   reintentos_max=reint if reint is not None else base.reintentos_max,
                   reintento_horas=float(espera) if espera is not None else base.reintento_horas,
                   intervalo_s=float(rev) if rev is not None else base.intervalo_s,
                   reprocesar_marca=str(fila.get("actualizado_en") or "") or None if v.get("reprocesar") is True else None)


class LectorAjustes:
    def __init__(self, tabla: Optional[Any] = None):
        self._t = tabla

    @classmethod
    def desde_entorno(cls) -> "LectorAjustes":
        return cls(tabla_desde_entorno("AJUSTES_TABLA_URL", "ajustes"))

    def leer(self) -> Optional[dict]:
        if self._t is None:
            return None
        try:
            return dict(self._t.get_entity(PK, RK))
        except Exception as exc:
            if type(exc).__name__ != "ResourceNotFoundError":
                log.warning("no se pudieron leer los ajustes: %s", type(exc).__name__)
            return None
