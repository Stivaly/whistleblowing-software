"""Genera las vistas previas HTML de los 5 correos del panel en kerna/operaciones/salida/correos/ (logo en línea, sin enviar nada).
Uso: python3 kerna/operaciones/generar_vistas_correo.py"""
import base64
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "kerna" / "front"))
from app import correo, logo  # noqa: E402

URL = "https://front-kerna-dev.azurewebsites.net/acceso"
EJEMPLOS = {
    "cuenta_creada": dict(usuario="m.fuentes", nombre="Marcela Fuentes", rol="Analista", clave_temporal="Rk7-Tq93-Lw4x-Pn2", url=URL),
    "clave_restablecida": dict(usuario="m.fuentes", nombre="Marcela Fuentes", clave_temporal="Hb5-Zm28-Cd6v-Yt9", url=URL),
    "cuenta_eliminada": dict(usuario="m.fuentes", nombre="Marcela Fuentes"),
    "rol_cambiado": dict(usuario="m.fuentes", nombre="Marcela Fuentes", rol="Administradora"),
    "clave_cambiada": dict(usuario="m.fuentes", nombre="Marcela Fuentes"),
}

if __name__ == "__main__":
    salida = Path(__file__).parent / "salida" / "correos"
    salida.mkdir(parents=True, exist_ok=True)
    src = "data:image/png;base64," + base64.b64encode(logo.png(112)).decode()
    for tipo, datos in EJEMPLOS.items():
        _, html, texto = correo.armar(tipo, datos, logo_src=src)
        (salida / f"{tipo}.html").write_text(html, encoding="utf-8")
        (salida / f"{tipo}.txt").write_text(texto, encoding="utf-8")
    print("vistas en", salida)
