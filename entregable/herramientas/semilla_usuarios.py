# Se ejecuta DENTRO del contenedor de Veridy de la semilla (lo llama construir.sh con docker exec).
# Deja la base lista para la instalación local de prueba:
#   - crea (o repara) los destinatarios de USUARIOS = "usuario|nombre|clave;..." asignados a todos los canales,
#     sin cambio de contraseña obligatorio y con su clave de cifrado;
#   - la copia de la semilla parte sin denuncias (las de prueba anteriores no las puede leer ninguna cuenta nueva);
#   - la cuenta del conector debe llamarse «Kerna AI…»: así la reconoce el bloque de Kerna en la vista del caso;
#   - quita el nombre de equipo fijo (hostname) y Tor, para que funcione en http://localhost en cualquier red.
# Imprime una línea por usuario (CREADA / EXISTE). Nunca imprime contraseñas.
import os

from globaleaks import models
from globaleaks.handlers.admin.user import db_create_user
from globaleaks.handlers.recipient.rtip import db_delete_itip
from globaleaks.models.config import ConfigFactory
from globaleaks.orm import get_session, set_db_uri
from globaleaks.utils.crypto import GCE

set_db_uri("sqlite:////var/globaleaks/globaleaks.db")
s = get_session()
try:
    cfg = ConfigFactory(s, 1)
    for var, val in (("hostname", "localhost"), ("tor", False), ("https_enabled", False)):
        cfg.set_val(var, val)
    for (itip,) in s.query(models.InternalTip.id).filter(models.InternalTip.tid == 1).all():
        db_delete_itip(s, itip)
    contextos = [c for (c,) in s.query(models.Context.id).filter(models.Context.tid == 1).all()]
    sal_base = cfg.get_val("receipt_salt")
    for linea in filter(None, os.environ["USUARIOS"].split(";")):
        usuario, nombre, clave = linea.split("|", 2)
        u = s.query(models.User).filter(models.User.tid == 1, models.User.username == usuario).first()
        estado = "EXISTE"
        if u is not None and u.name != nombre:
            u.name = u.public_name = nombre
            estado = "RENOMBRADA"
        if u is None:
            req = {"username": usuario, "name": nombre, "public_name": nombre, "description": "", "role": "receiver",
                   "mail_address": usuario.replace(".", "-") + "@veridy.local", "language": "es", "enabled": True,
                   "password_change_needed": False, "notification": False, "forcefully_selected": False,
                   "can_delete_submission": False, "can_postpone_expiration": True,
                   "can_grant_access_to_reports": usuario != "kerna-conector",
                   "can_transfer_access_to_reports": False, "can_redact_information": False,
                   "can_mask_information": False, "can_reopen_reports": usuario != "kerna-conector",
                   "can_edit_general_settings": False, "readonly": False,
                   "pgp_key_public": "", "pgp_key_remove": False, "pgp_key_fingerprint": "", "pgp_key_expiration": "",
                   "password": GCE.derive_key(clave, GCE.generate_salt(sal_base + ":" + usuario))}
            u = db_create_user(s, 1, None, req, "es")
            u.password_change_needed = False
            s.flush()
            estado = "CREADA"
        for ctx in contextos:
            if not s.query(models.ReceiverContext).filter(models.ReceiverContext.context_id == ctx,
                                                          models.ReceiverContext.receiver_id == u.id).first():
                s.add(models.ReceiverContext({"context_id": ctx, "receiver_id": u.id, "order": 0}))
        print(usuario, estado)
    s.commit()
finally:
    s.close()
