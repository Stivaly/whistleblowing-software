# Se ejecuta DENTRO del contenedor de Veridy local, que usa la base de Veridy en Azure.
# Crea (o repara) la cuenta receptora de prueba del instalador (USUARIO|NOMBRE|CLAVE en la variable AUDITOR),
# asignada a todos los canales, sin cambio de contraseña obligatorio, y permite que la cuenta del conector
# (kerna-conector) comparta casos. No borra denuncias ni cambia la configuración del sitio. Nunca imprime claves.
#   docker exec -i -e AUDITOR="usuario|nombre|clave" veridy-kerna-veridy-1 python3 - < entregable/herramientas/auditor_azure.py
import os

from globaleaks import models
from globaleaks.handlers.admin.user import db_create_user
from globaleaks.models.config import ConfigFactory
from globaleaks.orm import get_session, set_db_uri
from globaleaks.utils.crypto import GCE

set_db_uri(f"postgresql+psycopg2://veridy_app@{os.environ['VERIDY_PG_FQDN']}:5432/veridy?sslmode=verify-full&sslrootcert=system")
s = get_session()
try:
    usuario, nombre, clave = os.environ["AUDITOR"].split("|", 2)
    u = s.query(models.User).filter(models.User.tid == 1, models.User.username == usuario).first()
    estado = "EXISTE"
    if u is None:
        sal = ConfigFactory(s, 1).get_val("receipt_salt")
        req = {"username": usuario, "name": nombre, "public_name": nombre, "description": "", "role": "receiver",
               "mail_address": usuario.replace(".", "-") + "@veridy.local", "language": "es", "enabled": True,
               "password_change_needed": False, "notification": False, "forcefully_selected": False,
               "can_delete_submission": False, "can_postpone_expiration": True, "can_grant_access_to_reports": True,
               "can_transfer_access_to_reports": False, "can_redact_information": False, "can_mask_information": False,
               "can_reopen_reports": True, "can_edit_general_settings": False, "readonly": False,
               "pgp_key_public": "", "pgp_key_remove": False, "pgp_key_fingerprint": "", "pgp_key_expiration": "",
               "password": GCE.derive_key(clave, GCE.generate_salt(sal + ":" + usuario))}
        u = db_create_user(s, 1, None, req, "es")
        u.password_change_needed = False
        s.flush()
        estado = "CREADA"
    for (ctx,) in s.query(models.Context.id).filter(models.Context.tid == 1).all():
        if not s.query(models.ReceiverContext).filter(models.ReceiverContext.context_id == ctx,
                                                      models.ReceiverContext.receiver_id == u.id).first():
            s.add(models.ReceiverContext({"context_id": ctx, "receiver_id": u.id, "order": 0}))
    con = s.query(models.User).filter(models.User.tid == 1, models.User.username == "kerna-conector").one()
    con.can_grant_access_to_reports = True
    s.commit()
    print(usuario, estado, "| kerna-conector puede compartir")
finally:
    s.close()
