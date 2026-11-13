# Se ejecuta DENTRO del contenedor de Veridy (lo sube borrar_casos_invalidos.sh; la primera línea, MODO, la agrega él).
# Borra de Veridy los casos que Kerna no puede ni podrá procesar. Imprime solo conteos por motivo.
#
# Criterio «mal hecho» (se evalúa tras el reintento de todos: el conector deja en `error` lo que no pudo procesar):
#   sin_acceso  el caso no es accesible para la cuenta de servicio (Veridy no le dio la clave): no se puede leer ni reintentar.
#   sin_texto   el caso no tiene ningún texto de relato (vacío): no hay qué analizar.
#   ilegible    el caso no se pudo decodificar (`ilegible_*`).
# No se borra por resultado del núcleo (revisión manual, cadena agotada, validación fallida): son resultados legítimos
# y el caso puede servir en otra corrida. Los casos con error transitorio (red, núcleo) tampoco se tocan.
import json, os, sys, urllib.parse, urllib.request
import psycopg2

PERMANENTES = {"sin_acceso": "sin_acceso", "sin_texto": "sin_texto"}  # ilegible_* se agrega por prefijo
TOPE_DEFECTO = 10  # protección: no borrar más de esto sin --max


def secreto(nombre):
    cid, kv = os.environ["AZURE_CLIENT_ID"], os.environ["VERIDY_KV_URL"].rstrip("/")
    q = urllib.parse.urlencode({"api-version": "2018-02-01", "resource": "https://vault.azure.net", "client_id": cid})
    t = json.load(urllib.request.urlopen(urllib.request.Request(
        "http://169.254.169.254/metadata/identity/oauth2/token?" + q, headers={"Metadata": "true"}), timeout=10))["access_token"]
    return json.load(urllib.request.urlopen(urllib.request.Request(
        "%s/secrets/%s?api-version=7.4" % (kv, nombre), headers={"Authorization": "Bearer " + t}), timeout=30))["value"]


veridy = psycopg2.connect(os.environ["GLOBALEAKS_DB_URI"].replace("postgresql+psycopg2://", "postgresql://"))
conector = psycopg2.connect("postgresql://kerna_conector:%s@%s:5432/kerna_conector?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt"
                            % (urllib.parse.quote(secreto("conector-pg-password"), safe=""), os.environ["VERIDY_PG_FQDN"]))

cv, cc = veridy.cursor(), conector.cursor()
cc.execute("SELECT id_caso, ultimo_error FROM correspondencia_caso c WHERE estado = 'error' AND id_caso NOT IN "
           "(SELECT id_caso FROM objeto_procesado WHERE tipo = '_archivo' AND clave = 'ausente' AND id_nota = '1')")
en_error = cc.fetchall()
motivo_de, por_motivo, itips = {}, {}, {}
for id_caso, err in en_error:
    err = err or ""
    m = "ilegible" if err.startswith("ilegible_") else PERMANENTES.get(err)
    if not m:
        continue
    cv.execute("SELECT id FROM internaltip WHERE id = %s", (id_caso,))  # el id del conector es el del tip
    f = cv.fetchone()
    if not f:
        continue  # el caso ya no existe en Veridy
    itips[f[0]] = m
    por_motivo[m] = por_motivo.get(m, 0) + 1

cv.execute("SELECT count(*) FROM internaltip"); antes = cv.fetchone()[0]
resumen = {"modo": MODO, "casos_veridy_antes": antes, "casos_en_error_conector": len(en_error), "a_borrar": len(itips),
           "por_motivo": por_motivo}
if MODO == "aplicar" and itips:
    if len(itips) > TOPE_MAX:
        sys.exit("Se pedía borrar %d casos y el tope es %d: no se borra nada (usa --max N si es correcto)." % (len(itips), TOPE_MAX))
    for it, m in itips.items():
        cv.execute("DELETE FROM internaltip WHERE id = %s", (it,))  # receivertip, comentarios, respuestas y archivos caen en cascada
        cv.execute("INSERT INTO auditlog (tid, date, type, user_id, object_id, data) VALUES (1, now(), 'delete_report', NULL, %s, %s)",
                   (it, json.dumps({"motivo": m, "origen": "borrar_casos_invalidos"})))
    veridy.commit()
    cv.execute("SELECT count(*) FROM internaltip"); resumen["casos_veridy_despues"] = cv.fetchone()[0]
    resumen["borrados"] = len(itips)
print("RESUMEN " + json.dumps(resumen, sort_keys=True))
