# Se ejecuta DENTRO del contenedor de Veridy (lo sube crear_cuenta_e2e.sh; la primera línea, USUARIO/SECRETO, la agrega él).
# Crea un destinatario de Veridy con la misma función que usa la administración (db_create_user): clave de cifrado propia,
# contraseña leída de Key Vault (nunca se imprime) y asignación a los mismos canales que la cuenta de servicio del conector.
# Idempotente: si el usuario existe, solo repara su pertenencia a los canales. Imprime únicamente CREADA / EXISTE.
# Variable opcional CANALES (por defecto True): con False no se asigna a ningún canal (no recibe denuncias nuevas por sí solo).
import json, os, urllib.parse, urllib.request

from globaleaks import models
from globaleaks.handlers.admin.user import db_create_user
from globaleaks.orm import get_session, set_db_uri
from globaleaks.utils.crypto import GCE


def secreto(nombre):
    cid, kv = os.environ["AZURE_CLIENT_ID"], os.environ["VERIDY_KV_URL"].rstrip("/")
    q = urllib.parse.urlencode({"api-version": "2018-02-01", "resource": "https://vault.azure.net", "client_id": cid})
    t = json.load(urllib.request.urlopen(urllib.request.Request(
        "http://169.254.169.254/metadata/identity/oauth2/token?" + q, headers={"Metadata": "true"}), timeout=10))["access_token"]
    return json.load(urllib.request.urlopen(urllib.request.Request(
        "%s/secrets/%s?api-version=7.4" % (kv, nombre), headers={"Authorization": "Bearer " + t}), timeout=30))["value"]


CANALES = globals().get("CANALES", True)
set_db_uri(os.environ["GLOBALEAKS_DB_URI"])
s = get_session()
try:
    modelo = s.query(models.User).filter(models.User.tid == 1, models.User.username == "kerna-conector").one()
    u = s.query(models.User).filter(models.User.tid == 1, models.User.username == USUARIO).first()
    estado = "EXISTE"
    if u is None:
        pw = secreto(SECRETO)
        sal = GCE.generate_salt(models.config.ConfigFactory(s, 1).get_val("receipt_salt") + ":" + USUARIO)
        req = {"username": USUARIO, "name": NOMBRE, "public_name": NOMBRE, "description": "", "role": "receiver",
               "mail_address": modelo.mail_address, "language": modelo.language, "enabled": True,
               "password_change_needed": False, "notification": False, "forcefully_selected": False,
               "can_delete_submission": False, "can_postpone_expiration": False, "can_grant_access_to_reports": False,
               "can_transfer_access_to_reports": False, "can_redact_information": False, "can_mask_information": False,
               "can_reopen_reports": False, "can_edit_general_settings": False, "readonly": False,
               "pgp_key_public": "", "pgp_key_remove": False, "pgp_key_fingerprint": "", "pgp_key_expiration": "",
               "password": GCE.derive_key(pw, sal)}
        u = db_create_user(s, 1, None, req, modelo.language)
        s.flush()
        estado = "CREADA"
    for (ctx,) in (s.query(models.ReceiverContext.context_id).filter(models.ReceiverContext.receiver_id == modelo.id).all() if CANALES else []):
        if not s.query(models.ReceiverContext).filter(models.ReceiverContext.context_id == ctx, models.ReceiverContext.receiver_id == u.id).first():
            s.add(models.ReceiverContext({"context_id": ctx, "receiver_id": u.id, "order": 0}))
    s.commit()
    print(estado)
finally:
    s.close()
