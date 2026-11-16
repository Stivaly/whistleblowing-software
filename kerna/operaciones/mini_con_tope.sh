#!/usr/bin/env bash
# Mide gpt-5-mini (todas las etapas LLM) con tope de gasto. Solo mini; no repite las pruebas con nano.
# Uso: kerna/operaciones/mini_con_tope.sh [TOPE_USD=15]
# Orden: mx1 desarrollo (42) -> mx2 desarrollo_nuevo (206 difíciles) -> mx3 desarrollo (repetición, solo si queda presupuesto).
# El gasto se estima con los tokens de cada caso a precio de lista de mini (0,25/2,00 USD por millón) x 1,5 de margen;
# antes de cada paso se proyecta el costo del siguiente (tokens medios por caso x casos) y no se lanza si superaría el tope.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
TOPE="${1:-15}"; F=20261116; R=evaluacion/registro; LOG="$R/mini_tope_$F.log"
gasto() {  # suma USD (con margen) de los casos_cfg2_mx*_$F.json que existan
  python3 - "$R" "$F" <<'E'
import json,glob,sys
r,f=sys.argv[1:3]; t=0.0
for p in glob.glob(f"{r}/casos_cfg2_mx*_{f}.json"):
    for c in json.load(open(p)):
        t+=(int(c.get("tokens_entrada") or 0)*0.25+int(c.get("tokens_salida") or 0)*2.0)/1e6
print(round(t*1.5,2))
E
}
paso() {  # etiqueta set n_casos_estimado usd_estimado
  g=$(gasto); proy=$(python3 -c "print(round($g+$4,2))")
  echo "$(date +%T) $1 ($2): gastado est. $g USD, proyectado $proy USD, tope $TOPE" | tee -a "$LOG"
  if python3 -c "import sys;sys.exit(0 if $proy<=$TOPE else 1)"; then
    KERNA_CONCURRENCIA=2 operaciones/medicion_config_exp2.sh "$1" "$F" "$2" KERNA_MODELO_LLM=gpt-5-mini >> "$LOG" 2>&1
    echo "$(date +%T) $1 terminado; gastado est. $(gasto) USD" | tee -a "$LOG"
  else
    echo "$(date +%T) $1 NO se lanza: superaría el tope" | tee -a "$LOG"
  fi
}
paso mx1 desarrollo 0 2.6          # 42 casos: ~1,7 USD de lista x1,5
paso mx2 desarrollo_nuevo 0 10.5   # 206 casos: ~7 USD de lista x1,5
paso mx3 desarrollo 0 2.6
echo "$(date +%T) FIN; gastado est. $(gasto) USD" | tee -a "$LOG"
