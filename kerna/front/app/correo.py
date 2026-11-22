"""Correo del panel de Kerna AI: avisos de cuentas (creada, clave restablecida o cambiada, rol cambiado, eliminada).

Envía con el correo propio de Kerna en Azure Communication Services Email (infra/terraform/correo.tf): la cadena de
conexión llega en CORREO_ACS_CONEXION (referencia de Key Vault) y el remitente en CORREO_REMITENTE
(DoNotReply@<dominio administrado>.azurecomm.net). Si no está configurado, sirve un SMTP por variables de entorno
(SMTP_SERVIDOR, SMTP_PUERTO, SMTP_USUARIO, SMTP_CLAVE, SMTP_REMITENTE, SMTP_SEGURIDAD), útil en desarrollo.

`enviar(tipo, para, datos)` devuelve True si el servidor aceptó el mensaje y False ante cualquier falla. Nunca registra el
contenido del correo, la contraseña temporal ni las claves del SMTP: el log solo dice el tipo y la clase del error.
"""
from __future__ import annotations

import base64
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

log = logging.getLogger("kerna.correo")

PLANTILLAS = Path(__file__).parent / "plantillas" / "correo"
TIMEOUT = 10  # segundos: el panel no espera más a un SMTP caído
NOMBRE = "Kerna AI"
CID_LOGO = "logo-kerna"

# tipo -> (asunto, datos obligatorios)
TIPOS: dict[str, tuple[str, tuple[str, ...]]] = {
    "cuenta_creada": ("Tu cuenta en el panel de Kerna AI está lista", ("usuario", "nombre", "rol", "clave_temporal", "url")),
    "clave_restablecida": ("Restablecimos tu contraseña del panel de Kerna AI", ("usuario", "nombre", "clave_temporal", "url")),
    "cuenta_eliminada": ("Tu cuenta del panel de Kerna AI fue eliminada", ("usuario", "nombre")),
    "rol_cambiado": ("Cambió tu rol en el panel de Kerna AI", ("usuario", "nombre", "rol")),
    "clave_cambiada": ("Cambiaste tu contraseña del panel de Kerna AI", ("usuario", "nombre")),
}

_html = Environment(loader=FileSystemLoader(PLANTILLAS), autoescape=select_autoescape(["html"]), undefined=StrictUndefined)
_txt = Environment(loader=FileSystemLoader(PLANTILLAS), autoescape=False, undefined=StrictUndefined, keep_trailing_newline=True)

ultimo_codigo: int | None = None  # código SMTP de la última entrega (diagnóstico; no contiene datos)


@lru_cache(maxsize=1)
def _logo_png() -> bytes | None:
    try:
        from . import logo
        return logo.png(112)  # se muestra a 56 px: nítido en pantallas de alta densidad
    except Exception:
        return None


def _datos_validos(tipo: str, datos: dict) -> dict:
    _, requeridos = TIPOS[tipo]
    faltan = [k for k in requeridos if not str(datos.get(k, "")).strip()]
    if faltan:
        raise ValueError("faltan datos: " + ", ".join(faltan))
    limpio = {k: str(datos[k]) for k in requeridos}
    if "url" in limpio and not limpio["url"].lower().startswith(("https://", "http://")):
        limpio["url"] = ""  # nunca un enlace «javascript:» u otro esquema
    return limpio


def armar(tipo: str, datos: dict, logo_src: str | None = None) -> tuple[str, str, str]:
    """(asunto, html, texto) del correo. `logo_src` es el origen de la imagen del logo (por defecto el CID del adjunto en línea)."""
    if tipo not in TIPOS:
        raise ValueError("tipo de correo desconocido")
    d = _datos_validos(tipo, datos)
    asunto = TIPOS[tipo][0]
    contexto = {**d, "asunto": asunto, "logo_src": logo_src if logo_src is not None else f"cid:{CID_LOGO}"}
    return asunto, _html.get_template(f"{tipo}.html").render(contexto), _txt.get_template(f"{tipo}.txt").render(contexto)


def _config() -> dict | None:
    c = {k: os.environ.get(f"SMTP_{k.upper()}", "").strip() for k in ("servidor", "puerto", "usuario", "clave", "remitente", "seguridad")}
    if not (c["servidor"] and c["remitente"]):
        return None
    c["puerto"] = int(c["puerto"] or 587)
    c["seguridad"] = c["seguridad"].upper()
    return c


def _mensaje(cfg: dict, para: str, asunto: str, html: str, texto: str) -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = asunto
    m["From"] = formataddr((NOMBRE, cfg["remitente"]))
    m["To"] = para
    m["Message-ID"] = make_msgid(domain=cfg["remitente"].rpartition("@")[2] or None)
    m.set_content(texto)
    m.add_alternative(html, subtype="html")
    png = _logo_png()
    if png and f"cid:{CID_LOGO}" in html:
        m.get_payload()[1].add_related(png, "image", "png", cid=f"<{CID_LOGO}>", disposition="inline")
    return m


def _entregar(cfg: dict, m: EmailMessage, para: str) -> int:
    contexto = ssl.create_default_context()
    if cfg["seguridad"] == "SSL":
        smtp = smtplib.SMTP_SSL(cfg["servidor"], cfg["puerto"], timeout=TIMEOUT, context=contexto)
    else:
        smtp = smtplib.SMTP(cfg["servidor"], cfg["puerto"], timeout=TIMEOUT)
    with smtp:
        smtp.ehlo()
        if cfg["seguridad"] == "TLS":
            smtp.starttls(context=contexto)
            smtp.ehlo()
        if cfg["usuario"] and cfg["clave"]:
            smtp.login(cfg["usuario"], cfg["clave"])
        smtp.mail(cfg["remitente"])
        codigo, _ = smtp.rcpt(para)
        if codigo >= 300:
            return codigo
        codigo, _ = smtp.data(m.as_bytes())
        return codigo


def _acs() -> dict | None:
    """Configuración de Azure Communication Services Email, o None si no está (o si la referencia de Key Vault no se resolvió)."""
    conexion, remitente = os.environ.get("CORREO_ACS_CONEXION", "").strip(), os.environ.get("CORREO_REMITENTE", "").strip()
    if not conexion or not remitente or conexion.startswith("@Microsoft.KeyVault"):
        return None
    return {"conexion": conexion, "remitente": remitente}


def _entregar_acs(cfg: dict, para: str, asunto: str, html: str, texto: str) -> int:
    """Envía por Azure Communication Services. 202 si Azure aceptó y entregó el envío; 500 si no."""
    from azure.communication.email import EmailClient
    mensaje = {"senderAddress": cfg["remitente"], "recipients": {"to": [{"address": para}]},
               "content": {"subject": asunto, "plainText": texto, "html": html}}
    png = _logo_png()
    if png and f"cid:{CID_LOGO}" in html:   # el logo viaja como imagen en línea, igual que por SMTP
        mensaje["attachments"] = [{"name": "kerna.png", "contentType": "image/png", "contentInBase64": base64.b64encode(png).decode(),
                                   "contentId": CID_LOGO}]
    r = EmailClient.from_connection_string(cfg["conexion"]).begin_send(mensaje).result(timeout=4 * TIMEOUT)
    return 202 if str((r or {}).get("status", "")).lower() == "succeeded" else 500


def enviar(tipo: str, para: str, datos: dict) -> bool:
    """Envía el correo `tipo` a `para`. True si el servidor lo aceptó; False ante cualquier falla (sin excepciones)."""
    global ultimo_codigo
    ultimo_codigo = None
    try:
        acs, cfg = _acs(), _config()
        if acs is None and cfg is None:
            log.warning("correo %s no enviado: correo sin configurar", tipo)
            return False
        asunto, html, texto = armar(tipo, datos)
        if acs is not None:
            ultimo_codigo = _entregar_acs(acs, para.strip(), asunto, html, texto)
        else:
            ultimo_codigo = _entregar(cfg, _mensaje(cfg, para.strip(), asunto, html, texto), para.strip())
        ok = 200 <= ultimo_codigo < 300
        log.info("correo %s %s (%s %s)", tipo, "enviado" if ok else "rechazado", "ACS" if acs is not None else "SMTP", ultimo_codigo)
        return ok
    except Exception as e:  # nunca el mensaje de la excepción: puede traer la dirección o el servidor
        log.warning("correo %s no enviado (%s)", tipo, type(e).__name__)
        return False
