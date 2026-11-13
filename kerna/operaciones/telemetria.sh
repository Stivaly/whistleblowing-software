#!/usr/bin/env bash
# Consulta la telemetría de Kerna en Log Analytics (az monitor log-analytics query). Solo lee; solo conteos.
# Uso: kerna/operaciones/telemetria.sh <comando> [dias=7]
#   resumen [dias]      casos por día, cuántos pasaron a revisión manual y su %      (¿baja la revisión manual?)
#   reprocesos [dias]   reintentos y reprocesos del conector por día y estado        (¿se reprocesan los casos?)
#   motivos [dias]      casos en revisión manual por motivo
#   kql <archivo.kql|"consulta"> [dias]   cualquier consulta (archivo de kerna/docs/observabilidad/consultas o texto)
# Los eventos tardan unos minutos en aparecer en Log Analytics tras ocurrir.
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
CMD="${1:-}"; [ -n "$CMD" ] || { sed -n 2,10p "$0"; exit 2; }; shift
if [ "$CMD" = kql ]; then Q="${1:?falta la consulta}"; shift; fi
DIAS="${1:-7}"
WS="$(az monitor log-analytics workspace show -g "$RG" -n "${LOG_WS:-log-${RG#rg-}}" --query customerId -o tsv --only-show-errors)"
NUC='AppRoleName == "kerna.kerna-nucleo" and Message == "solicitud_terminada"'
case "$CMD" in
  resumen)    Q="AppTraces | where TimeGenerated > ago(${DIAS}d) and $NUC
| summarize casos=count(), revision_manual=countif(tostring(Properties.estado)==\"revision_manual\") by dia=bin(TimeGenerated,1d)
| extend pct_manual=round(100.0*revision_manual/casos,1) | order by dia asc" ;;
  reprocesos) Q="AppTraces | where TimeGenerated > ago(${DIAS}d) and AppRoleName == \"kerna.kerna-conector\" and Message in (\"conector_reintento\",\"conector_reproceso\")
| summarize eventos=count(), ultimo=max(TimeGenerated) by dia=bin(TimeGenerated,1d), evento=Message, estado=tostring(Properties.estado) | order by dia asc" ;;
  motivos)    Q="AppTraces | where TimeGenerated > ago(${DIAS}d) and $NUC and tostring(Properties.estado)==\"revision_manual\"
| summarize casos=count() by motivo=coalesce(tostring(Properties.motivo),\"sin_motivo\") | order by casos desc" ;;
  kql)        [ -f "$Q" ] && Q="$(sed "s/ago(7d)/ago(${DIAS}d)/g" "$Q")" ;;
  *) echo "comando desconocido: $CMD" >&2; exit 2 ;;
esac
az monitor log-analytics query -w "$WS" --analytics-query "$Q" -t "P${DIAS}D" -o table --only-show-errors
