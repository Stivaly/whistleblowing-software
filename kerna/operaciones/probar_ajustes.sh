#!/usr/bin/env bash
# Prueba de punta a punta los ajustes del panel en producción: guarda valores de prueba, verifica que el conector y el
# núcleo los apliquen y restaura los originales (también si algo falla). Solo usa az y curl; nunca imprime claves.
# Uso: kerna/operaciones/probar_ajustes.sh [--solo-panel] [--lote N]
#   CARGA_CMD="..."  comando que envía un caso nuevo en lugar del lote (p. ej. una denuncia de otro set de evaluación)
#   --lote N       tras guardar, carga el lote de N denuncias sintéticas para que el núcleo procese un caso nuevo (por defecto 2;
#                  es idempotente: si ese lote ya existe entero, súbelo en cada repetición: 3, 4, ...)
#   --restaurar-defectos   no prueba nada: deja Ajustes con los valores por defecto del esquema (úsalo si una corrida se cortó sin restaurar)
#   --solo-panel   solo guarda, comprueba la tabla y que el Resumen use la meta de respuesta guardada; restaura (no necesita Veridy)
# Requiere el front despierto, Veridy y el conector encendidos. Códigos: 0 todo bien, 1 algo falló, 2 conector o Veridy apagados.
set -uo pipefail
SOLO_PANEL=0; LOTE=2; DEFECTOS_SOLO=0
while [ $# -gt 0 ]; do case "$1" in --solo-panel) SOLO_PANEL=1;; --restaurar-defectos) DEFECTOS_SOLO=1;; --lote) shift; LOTE="${1:-2}";; esac; shift; done
AQUI="$(dirname "$0")"; . "$AQUI/_comun.sh"
CLAVE="$(clave_front vigente)" || exit 1
JAR="$(mktemp)"; ORIG="$(mktemp)"; trap 'restaurar; rm -f "$JAR" "$ORIG"' EXIT; FALLAS=0; RESTAURAR=0
c() { curl -sS --max-time 90 "$@"; }
ok() { echo "OK     $1"; }; mal() { echo "FALLA  $1"; FALLAS=$((FALLAS+1)); }

csrf_y_valores() {  # imprime el token CSRF y deja los valores actuales en $ORIG (JSON)
  c -b "$JAR" "$FRONT_URL/panel/ajustes" | python3 -c '
import re, sys, json, html
h = sys.stdin.read()
m = re.search(r"name=\"csrf\" value=\"([^\"]+)\"", h)
d = re.search(r"<script type=\"application/json\" id=\"ajustes-datos\">(.*?)</script>", h, re.S)
print(m.group(1) if m else "")
if d:
    open(sys.argv[1], "w").write(json.dumps(json.loads(html.unescape(d.group(1)))["valores"]))
' "${1:-$ORIG}"
}
guardar() {  # guardar <json>: POST como lo hace la página
  local T; T="$(csrf_y_valores /dev/null)"
  [ -n "$T" ] || { echo "sin token"; return 1; }
  c -b "$JAR" -X POST -H 'Accept: application/json' -H "Origin: $FRONT_URL" --data-urlencode "csrf=$T" --data-urlencode "valores=$1" "$FRONT_URL/panel/ajustes"
}
restaurar() {
  [ "$RESTAURAR" = 1 ] || return 0
  RESTAURAR=0
  if [ -s "$ORIG" ] && grep -q '"estado": \?"ok"' <<<"$(guardar "$(cat "$ORIG")")"; then echo "OK     valores originales restaurados"
  else echo "FALLA  no se pudieron restaurar los valores originales (revisa Ajustes en el panel)"; FALLAS=$((FALLAS+1)); fi
}

R="$(c -o /dev/null -c "$JAR" -w '%{http_code}' --data-urlencode "usuario=admin" --data-urlencode "clave=$CLAVE" "$FRONT_URL/acceso")"
[ "$R" = 303 ] && grep -q kerna_panel "$JAR" && ok "inicio de sesión en el panel" || { mal "inicio de sesión dio $R"; exit 1; }
csrf_y_valores >/dev/null
if [ "$DEFECTOS_SOLO" = 1 ]; then
  DEF="$(PYTHONPATH="$AQUI/../comun" python3 -c 'import json; from kerna_comun.ajustes_esquema import DEFECTOS; print(json.dumps(DEFECTOS))')"
  grep -q '"estado": \?"ok"' <<<"$(guardar "$DEF")" && { ok "Ajustes quedó con los valores por defecto"; exit 0; } || { mal "no se pudieron guardar los valores por defecto"; exit 1; }
fi
mkdir -p "$AQUI/salida"; cp "$ORIG" "$AQUI/salida/ajustes_antes_de_prueba.json" 2>/dev/null  # copia que sobrevive a un corte
[ -s "$ORIG" ] && ok "valores actuales guardados para restaurar" || { mal "no se pudieron leer los valores actuales"; exit 1; }
RESTAURAR=1
PRUEBA='{"envios":7,"reintentos":2,"espera":12,"revision":60,"reprocesar":false,"evaluador":true,"candidatos":40,"cadena":[{"v":"gemini","on":true},{"v":"azure","on":true}],"compartir":[],"maxresp":20,"alerta":1}'
grep -q '"estado": \?"ok"' <<<"$(guardar "$PRUEBA")" && ok "valores de prueba guardados desde el panel" || { mal "no se pudieron guardar los valores de prueba"; exit 1; }
grep -q 'candidatos[^0-9]*40' <<<"$("$AQUI/tablas.sh" ajustes)" && ok "la fila de ajustes quedó guardada" || mal "la fila de ajustes no muestra los valores de prueba"

grep -q 'meta 20 s' <<<"$(c -b "$JAR" "$FRONT_URL/panel")" && ok "el Resumen usa la meta de respuesta guardada (20 s)" || mal "el Resumen no muestra la meta de 20 s"
if [ "$SOLO_PANEL" = 1 ]; then
  restaurar
  grep -q 'candidatos[^0-9]*40' <<<"$("$AQUI/tablas.sh" ajustes)" && mal "la fila sigue con los valores de prueba" || ok "la fila quedó con los valores originales"
  [ "$FALLAS" = 0 ] && echo "Todo bien (solo panel)." || { echo "$FALLAS prueba(s) fallaron."; exit 1; }
  exit 0
fi

# El conector aplica en su próxima pasada (hasta 3 min)
FILA_Q="PartitionKey eq 'kerna' and RowKey eq 'conector'"
conector_ok() {
  "$AQUI/tablas.sh" ver reintentosmanuales "$FILA_Q" | python3 -c '
import sys, json
f = json.load(sys.stdin); f = f[0] if f else {}
esp = {"ajustes_de_tabla": True, "envios_max": 7, "reintentos_max": 2, "espera_h": 12, "intervalo_s": 60, "alerta_h": 1}
ok = all(str(f.get(k)).lower() == str(v).lower() for k, v in esp.items()) and str(f.get("equipos", "")) == ""
sys.exit(0 if ok else 1)'
}
if [ -z "$("$AQUI/tablas.sh" ver reintentosmanuales "$FILA_Q" | tr -d '[] \n')" ]; then
  echo "El conector no ha escrito su estado: Veridy o el conector están apagados."; exit 2
fi
FIN=$((SECONDS+180)); HECHO=0
while [ $SECONDS -lt $FIN ]; do conector_ok && { HECHO=1; break; }; sleep 10; done
[ "$HECHO" = 1 ] && ok "el conector aplicó envíos, reintentos, espera, revisión, alerta y equipos (nadie)" || mal "el conector no mostró los valores de prueba en 3 min"

# El núcleo registra `ajustes_aplicados` al ver el guardado (los eventos tardan minutos)
KQL='AppTraces | where TimeGenerated > ago(30m) and Message == "ajustes_aplicados" | where tostring(Properties.candidatos) == "40" and tostring(Properties.cadena) == "gemini>azure" | count'
FIN=$((SECONDS+480)); HECHO=0
echo "       (el núcleo ve el guardado al procesar un caso: cargo el lote $LOTE; los eventos tardan minutos en la telemetría)"
if [ -n "${CARGA_CMD:-}" ]; then bash -c "$CARGA_CMD" 2>&1 | tail -2; else "$AQUI/cargar_denuncias.sh" "$LOTE" 2>&1 | tail -2; fi
while [ $SECONDS -lt $FIN ]; do
  N="$("$AQUI/telemetria.sh" kql "$KQL" 1 2>/dev/null | grep -Eo '[0-9]+' | tail -1)"
  [ "${N:-0}" -gt 0 ] && { HECHO=1; break; }; sleep 20
done
[ "$HECHO" = 1 ] && ok "el núcleo aplicó candidatos=40 y cadena gemini>azure" || mal "el núcleo no registró ajustes_aplicados con los valores de prueba en 8 min"

restaurar
grep -q 'candidatos[^0-9]*40' <<<"$("$AQUI/tablas.sh" ajustes)" && mal "la fila sigue con los valores de prueba" || ok "la fila quedó con los valores originales"
[ "$FALLAS" = 0 ] && echo "Todo bien." || { echo "$FALLAS prueba(s) fallaron."; exit 1; }
