"""Punto de entrada: `python -m kerna_conector [--una-pasada]`.

Códigos de salida de `--una-pasada`: 0 todo bien, 1 la pasada terminó con errores o con el núcleo caído,
2 error de configuración, 3 la pasada se omitió porque otra estaba en curso.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading

from kerna_comun import telemetria

from .ajustes import APLICADOS, LectorAjustes, parametros
from .config import Config, ErrorConfiguracion
from .estado import abrir_estado
from .nucleo import ClienteNucleo
from .reconciliacion import ejecutar_pasada
from .solicitudes import SolicitudReintento
from .veridy import ClienteVeridy

log = logging.getLogger("kerna.conector")


def _vivo(estado, r, p, en_reintento: bool) -> dict:
    """Fila de estado en vivo (`reintentosmanuales`, kerna/conector): solo conteos, nunca textos ni ids de casos."""
    por = estado.contar_estados()
    revision = estado.contar_objetos("resultado", "actual", "revision_manual", prefijo_nota=True)
    conocidos = estado.contar_objetos("resultado", "actual", None)
    return {"ultima_pasada": r.resultado, "casos": r.casos, "archivados": estado.contar_archivados(), "nuevo": por.get("nuevo", 0), "pendiente": por.get("pendiente", 0),
            "error": por.get("error", 0), "completado": por.get("completado", 0), "en_revision_manual": revision,
            "resultado_desconocido": max(0, por.get("completado", 0) - conocidos), "nucleo_caido": bool(r.nucleo_caido),
            "enviados": r.enviados, "sugerencias": r.sugerencias, "errores": r.errores, "en_reintento": en_reintento,
            "intervalo_s": int(p.intervalo_s), "ajustes_de_tabla": bool(p.de_ajustes),
            "ajustes_aplicados": ",".join(APLICADOS), "envios_max": p.envios_max, "reintentos_max": p.reintentos_max,
            "espera_h": int(p.reintento_horas)}


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
    solicitud = SolicitudReintento.desde_entorno()
    lector_ajustes = LectorAjustes.desde_entorno()
    en_vuelo_max = int(os.environ.get("KERNA_MANUAL_EN_VUELO", "12") or 12)
    codigo = 0
    try:
        while not parar.is_set():
            espera = cfg.intervalo_s
            try:
                p = parametros(cfg, lector_ajustes.leer())
                espera = p.intervalo_s
                if p.reprocesar_marca and not estado.objeto_procesado("_ajustes", "reprocesar", p.reprocesar_marca):
                    estado.marcar_procesado("_ajustes", "reprocesar", p.reprocesar_marca)
                    solicitud.solicitar("ajustes")  # «Reintentar los de revisión manual»: una vez por guardado
                corrida = solicitud.activa()
                r = ejecutar_pasada(veridy, nucleo, estado, cfg.id_empresa, compartir_con=cfg.compartir_con,
                                    reprocesar=cfg.reprocesar, reintentos_max=p.reintentos_max,
                                    reintento_horas=p.reintento_horas, envios_max=p.envios_max, corrida=corrida,
                                    en_vuelo_max=en_vuelo_max)
                if corrida is not None and not r.omitida:
                    espera = min(espera, 10.0)  # con una corrida en curso se mira el avance seguido
                    if r.manual_completa:
                        solicitud.terminar(corrida, r.manual_total, r.manual_fin, r.manual_con)
                        log.info("reintento manual terminado: reintentados=%d con_sugerencia=%d", r.manual_fin, r.manual_con)
                    else:
                        solicitud.progreso(corrida, r.manual_total, estado.contar_objetos("manual", corrida.id + ":enviado"),
                                           r.manual_fin, r.manual_con, r.manual_en_vuelo)
                if not r.omitida:
                    solicitud.publicar_vivo(_vivo(estado, r, p, corrida is not None))
                log.info("pasada: %s casos=%d enviados=%d sugerencias=%d reenviados=%d reprocesados=%d decisiones=%d errores=%d",
                         r.resultado, r.casos, r.enviados, r.sugerencias, r.reenviados, r.reprocesados, r.decisiones, r.errores)
                codigo = 3 if r.omitida else (0 if r.exitosa else 1)
            except Exception as exc:  # el bucle no muere por una pasada
                log.error("pasada fallida: %s", type(exc).__name__)
                codigo = 1
            if args.una_pasada:
                break
            parar.wait(espera)
    finally:
        veridy.cerrar_sesion()
        estado.cerrar()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
