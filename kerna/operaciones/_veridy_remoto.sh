#!/usr/bin/env bash
# Funciones compartidas (se carga con `source`): ejecutar un script de Python DENTRO del contenedor de Veridy
# (tiene GLOBALEAKS_DB_URI, la identidad administrada y el código de GlobaLeaks), sin dejar nada en disco local.
# `az container exec` parte la orden por espacios y limita su largo: el script viaja comprimido en base64 y en trozos de 300 caracteres (la orden admite ~390 y convierte «+» en espacio: base64 seguro para URL).
RAIZ="${RAIZ:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)}"
TF_VERIDY="$RAIZ/infra/veridy/terraform"
tf_veridy() { terraform -chdir="$TF_VERIDY" output -raw "$1"; }
RG_V="${RG_V:-$(tf_veridy grupo_recursos)}"
ACI_V="${ACI_V:-$(tf_veridy contenedor)}"
KV_V="${KV_V:-$(tf_veridy key_vault_nombre)}"
URL_V="${URL_V:-$(tf_veridy url)}"; URL_V="${URL_V%/}"

veridy_encendido() {
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$URL_V/api/health" || true)" = 200 ] \
    || { echo "Veridy no responde. Enciéndelo con: infra/veridy/veridy.sh encender" >&2; return 1; }
}

_exec_v() { timeout 120 az container exec -g "$RG_V" -n "$ACI_V" --container-name veridy --exec-command "$1" --only-show-errors; }

# remoto_py <archivo.py>: sube el script al contenedor (verificando su sha256; reintenta si un trozo llega alterado) y lo
# ejecuta; devuelve su salida.
remoto_py() {
  local b64 h i n=300 f intento ok=0
  b64="$(python3 -c 'import sys,zlib,base64;print(base64.urlsafe_b64encode(zlib.compress(open(sys.argv[1],"rb").read(),9)).decode())' "$1")"
  h="$(printf '%s' "$b64" | sha256sum | cut -c1-64)"
  for intento in 1 2 3; do
    f="/tmp/gl_r_$$_$RANDOM.b64"; i=0
    while [ $i -lt ${#b64} ]; do
      _exec_v "python3 -c open('$f','a').write('${b64:$i:$n}')" >/dev/null 2>&1 || true; i=$((i+n))
    done
    if [ "$(_exec_v "python3 -c print(__import__('hashlib').sha256(open('$f','rb').read()).hexdigest())" 2>/dev/null | tr -d '\r')" = "$h" ]; then ok=1; break; fi
    _exec_v "python3 -c __import__('os').remove('$f')" >/dev/null 2>&1 || true
  done
  [ $ok = 1 ] || { echo "No se pudo subir el script al contenedor." >&2; return 1; }
  _exec_v "python3 -c exec(__import__('zlib').decompress(__import__('base64').urlsafe_b64decode(open('$f').read())))" | tr -d '\r'
  _exec_v "python3 -c __import__('os').remove('$f')" >/dev/null || true
}
