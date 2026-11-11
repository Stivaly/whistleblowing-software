"""Punto de entrada: `python -m kerna_conector [--una-pasada]`.

Códigos de salida de `--una-pasada`: 0 todo bien, 1 la pasada terminó con errores o con el núcleo caído,
2 error de configuración, 3 la pasada se omitió porque otra estaba en curso.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading

from kerna_comun import telemetria

from .config import Config, ErrorConfiguracion
from .estado import abrir_estado
from .nucleo import ClienteNucleo
from .reconciliacion import ejecutar_pasada
from .veridy import ClienteVeridy

log = logging.getLogger("kerna.conector")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="kerna_conector", description="Conector Veridy de Kerna AI")
    parser.add_argument("--una-pasada", action="store_true", help="ejecuta una sola pasada y sale")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        cfg = Config.desde_entorno()
    except ErrorConfiguracion as exc:
        log.error("configuración incompleta: %s", exc)
        return 2

    telemetria.configurar("kerna-conector")
    parar = threading.Event()
    for senal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(senal, lambda *_: parar.set())

    veridy = ClienteVeridy(cfg.veridy_url, cfg.veridy_usuario, cfg.veridy_password, cfg.veridy_tid)
    nucleo = ClienteNucleo(cfg.kerna_api_url, cfg.kerna_client_id, cfg.kerna_client_secret, cfg.id_empresa,
                           dormir=lambda s: parar.wait(s))
    estado = abrir_estado(cfg.estado)
    codigo = 0
    try:
        while not parar.is_set():
            try:
                r = ejecutar_pasada(veridy, nucleo, estado, cfg.id_empresa)
                log.info("pasada: %s casos=%d enviados=%d sugerencias=%d decisiones=%d errores=%d",
                         r.resultado, r.casos, r.enviados, r.sugerencias, r.decisiones, r.errores)
                codigo = 3 if r.omitida else (0 if r.exitosa else 1)
            except Exception as exc:  # el bucle no muere por una pasada
                log.error("pasada fallida: %s", type(exc).__name__)
                codigo = 1
            if args.una_pasada:
                break
            parar.wait(cfg.intervalo_s)
    finally:
        veridy.cerrar_sesion()
        estado.cerrar()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
