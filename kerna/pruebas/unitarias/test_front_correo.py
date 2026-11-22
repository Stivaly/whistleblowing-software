"""Correo del panel (front/app/correo.py): asunto, HTML y texto de cada tipo; SMTP simulado; sin secretos en logs; False ante fallas; escapado."""
import logging
import re
import sys
from email import message_from_bytes, policy
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
from app import correo  # noqa: E402

CLAVE_SMTP = "clave-smtp-secreta-123"
CLAVE_TEMP = "Tmp-Zq81-Wx5k"
URL = "https://panel.ejemplo.cl/acceso"
DATOS = {
    "cuenta_creada": dict(usuario="m.fuentes", nombre="Marcela Fuentes", rol="Analista", clave_temporal=CLAVE_TEMP, url=URL),
    "clave_restablecida": dict(usuario="m.fuentes", nombre="Marcela Fuentes", clave_temporal=CLAVE_TEMP, url=URL),
    "cuenta_eliminada": dict(usuario="m.fuentes", nombre="Marcela Fuentes"),
    "rol_cambiado": dict(usuario="m.fuentes", nombre="Marcela Fuentes", rol="Administradora"),
    "clave_cambiada": dict(usuario="m.fuentes", nombre="Marcela Fuentes"),
}


@pytest.fixture
def smtp_env(monkeypatch):
    for k, v in dict(SERVIDOR="smtp.ejemplo.cl", PUERTO="587", USUARIO="usuario-smtp", CLAVE=CLAVE_SMTP,
                     REMITENTE="avisos@ejemplo.cl", SEGURIDAD="TLS").items():
        monkeypatch.setenv(f"SMTP_{k}", v)


@pytest.fixture
def smtp(monkeypatch):
    """smtplib simulado: devuelve (clase SMTP, clase SMTP_SSL, la conexión simulada)."""
    con = MagicMock()
    con.__enter__.return_value = con
    con.rcpt.return_value = (250, b"ok")
    con.data.return_value = (250, b"queued")
    clase, clase_ssl = MagicMock(return_value=con), MagicMock(return_value=con)
    monkeypatch.setattr(correo.smtplib, "SMTP", clase)
    monkeypatch.setattr(correo.smtplib, "SMTP_SSL", clase_ssl)
    return clase, clase_ssl, con


@pytest.mark.parametrize("tipo", list(DATOS))
def test_cada_tipo_arma_asunto_html_y_texto(tipo):
    asunto, html, texto = correo.armar(tipo, DATOS[tipo])
    assert asunto and asunto == correo.TIPOS[tipo][0]
    assert html.lstrip().lower().startswith("<!doctype html") and "Marcela Fuentes" in html and "m.fuentes" in html
    assert "Marcela Fuentes" in texto and "m.fuentes" in texto and "<" not in texto
    assert "avisa a Dirección" in html and "avisa a Dirección" in texto
    assert "#1C2A6B" in html and "#CFFF5E" in html and "cid:logo-kerna" in html  # paleta e identidad de Kerna
    assert "Unbounded" in html and "JetBrains Mono" in html and "Arial" in html  # tipografías con respaldo seguro


def test_cuentas_con_clave_temporal_dicen_que_hacer():
    for tipo in ("cuenta_creada", "clave_restablecida"):
        _, html, texto = correo.armar(tipo, DATOS[tipo])
        assert CLAVE_TEMP in html and CLAVE_TEMP in texto and URL in html and URL in texto
        assert "te pedirá cambiarla" in texto
    for tipo in ("cuenta_eliminada", "rol_cambiado", "clave_cambiada"):
        assert CLAVE_TEMP not in "".join(correo.armar(tipo, DATOS[tipo]))


def test_rol_cambiado_muestra_el_rol():
    _, html, texto = correo.armar("rol_cambiado", DATOS["rol_cambiado"])
    assert "Administradora" in html and "Administradora" in texto


def test_escapa_los_datos_en_html():
    d = {**DATOS["cuenta_creada"], "nombre": '<script>alert(1)</script>', "usuario": 'a"><img src=x>', "rol": "<b>x</b>"}
    _, html, texto = correo.armar("cuenta_creada", d)
    assert "<script>" not in html and "<img src=x>" not in html and "<b>x</b>" not in html
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" in texto  # el texto plano no es HTML: va tal cual


def test_enlace_solo_http_o_https():
    d = {**DATOS["cuenta_creada"], "url": "javascript:alert(1)"}
    _, html, texto = correo.armar("cuenta_creada", d)
    assert "javascript:" not in html and "javascript:" not in texto and "href=" not in html


def test_datos_faltantes_o_tipo_desconocido_fallan_al_armar():
    with pytest.raises(ValueError):
        correo.armar("cuenta_creada", {"usuario": "x"})
    with pytest.raises(ValueError):
        correo.armar("no_existe", {})


def test_envia_con_starttls_login_remitente_y_partes(smtp_env, smtp):
    clase, clase_ssl, con = smtp
    assert correo.enviar("cuenta_creada", "m.fuentes@ejemplo.cl", DATOS["cuenta_creada"]) is True
    assert clase.call_args.args[:2] == ("smtp.ejemplo.cl", 587) and clase.call_args.kwargs["timeout"] == correo.TIMEOUT
    clase_ssl.assert_not_called()
    con.starttls.assert_called_once()
    con.login.assert_called_once_with("usuario-smtp", CLAVE_SMTP)
    con.mail.assert_called_once_with("avisos@ejemplo.cl")
    con.rcpt.assert_called_once_with("m.fuentes@ejemplo.cl")
    m = message_from_bytes(con.data.call_args.args[0], policy=policy.default)
    assert m["From"] == "Kerna AI <avisos@ejemplo.cl>" and m["To"] == "m.fuentes@ejemplo.cl"
    assert m["Subject"] == correo.TIPOS["cuenta_creada"][0]
    tipos = [p.get_content_type() for p in m.walk()]
    assert "text/plain" in tipos and "text/html" in tipos and "image/png" in tipos  # logo embebido por CID
    assert m.get_body(("plain",)).get_content().count(CLAVE_TEMP) == 1
    assert "cid:logo-kerna" in m.get_body(("html",)).get_content()


def test_ssl_usa_smtp_ssl_sin_starttls(smtp_env, smtp, monkeypatch):
    monkeypatch.setenv("SMTP_SEGURIDAD", "ssl")
    monkeypatch.setenv("SMTP_PUERTO", "465")
    clase, clase_ssl, con = smtp
    assert correo.enviar("clave_cambiada", "a@ejemplo.cl", DATOS["clave_cambiada"]) is True
    clase.assert_not_called()
    assert clase_ssl.call_args.args[:2] == ("smtp.ejemplo.cl", 465)
    con.starttls.assert_not_called()


def test_sin_usuario_no_inicia_sesion(smtp_env, smtp, monkeypatch):
    monkeypatch.setenv("SMTP_USUARIO", "")
    assert correo.enviar("clave_cambiada", "a@ejemplo.cl", DATOS["clave_cambiada"]) is True
    smtp[2].login.assert_not_called()


@pytest.mark.parametrize("falla", ["conexion", "login", "destinatario_rechazado", "data_rechazado"])
def test_false_ante_cualquier_falla(smtp_env, smtp, falla):
    clase, _, con = smtp
    if falla == "conexion":
        clase.side_effect = OSError("sin red")
    elif falla == "login":
        con.login.side_effect = correo.smtplib.SMTPAuthenticationError(535, b"mala clave")
    elif falla == "destinatario_rechazado":
        con.rcpt.return_value = (550, b"no existe")
    else:
        con.data.return_value = (554, b"rechazado")
    assert correo.enviar("cuenta_creada", "a@ejemplo.cl", DATOS["cuenta_creada"]) is False


def test_false_sin_configuracion_con_datos_malos_o_destino_invalido(smtp_env, smtp, monkeypatch):
    assert correo.enviar("cuenta_creada", "a@ejemplo.cl", {"usuario": "x"}) is False
    assert correo.enviar("tipo_raro", "a@ejemplo.cl", {}) is False
    assert correo.enviar("clave_cambiada", "a@ejemplo.cl\nBcc: otro@x.cl", DATOS["clave_cambiada"]) is False  # sin inyección de cabeceras
    smtp[2].data.assert_not_called()
    monkeypatch.delenv("SMTP_SERVIDOR")
    assert correo.enviar("clave_cambiada", "a@ejemplo.cl", DATOS["clave_cambiada"]) is False


def test_los_logs_no_llevan_secretos_ni_contenido(smtp_env, smtp, caplog):
    caplog.set_level(logging.DEBUG)
    con = smtp[2]
    correo.enviar("cuenta_creada", "m.fuentes@ejemplo.cl", DATOS["cuenta_creada"])  # éxito
    con.login.side_effect = correo.smtplib.SMTPAuthenticationError(535, CLAVE_SMTP.encode())
    correo.enviar("clave_restablecida", "m.fuentes@ejemplo.cl", DATOS["clave_restablecida"])  # falla con la clave en el error
    texto = "\n".join(r.getMessage() + str(r.exc_info) for r in caplog.records)
    assert caplog.records
    for secreto in (CLAVE_SMTP, CLAVE_TEMP, "usuario-smtp", "m.fuentes", "Marcela", "ejemplo.cl"):
        assert secreto not in texto
    assert re.search(r"cuenta_creada enviado", texto) and "SMTPAuthenticationError" in texto
