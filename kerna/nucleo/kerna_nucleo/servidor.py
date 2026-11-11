"""Arranque con uvicorn: `python -m kerna_nucleo`."""
from __future__ import annotations

import os

import uvicorn

from kerna_comun import telemetria

from .api import crear_app
from .config import Config


def main() -> None:
    telemetria.configurar("kerna-nucleo")
    app = crear_app(Config.desde_entorno())
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), log_level="info")


if __name__ == "__main__":
    main()
