"""Configuración del conector a partir de variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


class ErrorConfiguracion(Exception):
    pass


_OBLIGATORIAS = ("VERIDY_URL", "VERIDY_USUARIO", "VERIDY_PASSWORD", "KERNA_API_URL",
                 "KERNA_CLIENT_ID", "KERNA_CLIENT_SECRET")


def _entero(valor, defecto: int) -> int:
    try:
        return max(0, int(str(valor).strip()))
    except (TypeError, ValueError):
        return defecto


@dataclass(frozen=True)
class Config:
    veridy_url: str
    veridy_usuario: str
    veridy_password: str = field(repr=False)
    kerna_api_url: str
    kerna_client_id: str
    kerna_client_secret: str = field(repr=False)
    veridy_tid: int = 0
    id_empresa: str = "veridy"
    intervalo_s: float = 30.0
    estado: str = "sqlite:///conector.db"
    compartir_con: str = ""
    reprocesar: bool = False
    reintentos_max: int = 3
    reintento_horas: float = 24.0
    envios_por_pasada: int = 5

    @classmethod
    def desde_entorno(cls, entorno=None) -> "Config":
        e = os.environ if entorno is None else entorno
        faltan = [v for v in _OBLIGATORIAS if not e.get(v)]
        if faltan:
            raise ErrorConfiguracion("faltan variables: " + ", ".join(faltan))
        try:
            tid = int(e.get("VERIDY_TID", "0"))
            maxr = int(e.get("KERNA_REINTENTOS_MAX", "3"))
            horas = float(e.get("KERNA_REINTENTO_HORAS", "24"))
            intervalo = float(e.get("CONECTOR_INTERVALO_S", "30"))
        except ValueError as exc:
            raise ErrorConfiguracion("VERIDY_TID o CONECTOR_INTERVALO_S no son numéricos") from exc
        if intervalo <= 0:
            raise ErrorConfiguracion("CONECTOR_INTERVALO_S debe ser positivo")
        return cls(
            veridy_url=e["VERIDY_URL"].rstrip("/"),
            veridy_usuario=e["VERIDY_USUARIO"],
            veridy_password=e["VERIDY_PASSWORD"],
            kerna_api_url=e["KERNA_API_URL"].rstrip("/"),
            kerna_client_id=e["KERNA_CLIENT_ID"],
            kerna_client_secret=e["KERNA_CLIENT_SECRET"],
            veridy_tid=tid,
            id_empresa=e.get("KERNA_ID_EMPRESA", "veridy"),
            intervalo_s=intervalo,
            estado=e.get("CONECTOR_ESTADO", "sqlite:///conector.db"),
            compartir_con=e.get("VERIDY_COMPARTIR_CON", "").strip(),
            envios_por_pasada=_entero(e.get("KERNA_ENVIOS_POR_PASADA"), 5),
            reintentos_max=maxr,
            reintento_horas=horas,
            reprocesar=e.get("KERNA_REPROCESAR_REVISION_MANUAL", "").strip() in ("1", "true", "si"),
        )
