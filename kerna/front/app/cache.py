"""Caché compartida con refresco en segundo plano (stale-while-revalidate) y ejecución en paralelo.

La petición nunca espera a Log Analytics si ya hubo un cálculo reciente: devuelve el dato guardado y,
si está vencido, lo recalcula en un hilo aparte. Solo la primera carga de cada clave espera."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

_datos: dict = {}
_candado = threading.Lock()
_enproceso: set = set()
POOL = ThreadPoolExecutor(max_workers=12, thread_name_prefix="kerna")


def paralelo(tareas: dict[str, Callable]) -> dict:
    """Ejecuta funciones sin argumentos a la vez; devuelve {nombre: resultado} o {nombre: Exception}."""
    fut = {n: POOL.submit(f) for n, f in tareas.items()}
    out = {}
    for n, f in fut.items():
        try:
            out[n] = f.result()
        except Exception as e:  # el que llama decide qué hacer con cada fallo
            out[n] = e
    return out


def _calcular(clave, fn):
    try:
        v = fn()
        _datos[clave] = (time.time(), v)
    finally:
        with _candado:
            _enproceso.discard(clave)


def obtener(clave, fn: Callable, ttl: float = 60, vida_max: float = 3600):
    """Dato fresco si lo hay; vencido pero útil (< vida_max) se entrega y se refresca aparte; si no, se calcula esperando."""
    hit = _datos.get(clave)
    ahora = time.time()
    if hit and ahora - hit[0] < ttl:
        return hit[1]
    if hit and ahora - hit[0] < vida_max:
        with _candado:
            if clave not in _enproceso:
                _enproceso.add(clave)
                POOL.submit(_calcular, clave, fn)
        return hit[1]
    v = fn()
    _datos[clave] = (time.time(), v)
    return v


def hay(clave, vida_max: float = 3600) -> bool:
    hit = _datos.get(clave)
    return bool(hit and time.time() - hit[0] < vida_max)


def precalentar(tareas: list[tuple]) -> None:
    """Lanza en segundo plano `obtener(clave, fn, ttl)` para cada tarea (al arrancar); los errores se ignoran."""
    def _uno(clave, fn, ttl):
        try:
            obtener(clave, fn, ttl)
        except Exception:
            pass
    for clave, fn, ttl in tareas:
        POOL.submit(_uno, clave, fn, ttl)


def vaciar() -> None:
    _datos.clear()
    with _candado:
        _enproceso.clear()
