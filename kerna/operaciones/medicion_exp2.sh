#!/usr/bin/env bash
# Experimento 2 (generador y reranker): corre la cadena sobre un set con la mejor configuración de ebm y flags extra.
# Uso: kerna/operaciones/medicion_exp2.sh ETIQUETA AAAAMMDD set [VAR=valor ...]
#   Salida: kerna/evaluacion/registro/casos_exp2_<ETIQUETA>_<set>_<fecha>.json (con evaluador_orden, orden_generador y
#   generador: solo IDs, puntajes y motivos de rechazo). Reanuda hasta 3 veces los casos con cadena agotada (429).
#   En prueba3 el revisor no aplica la causal hechos_fuera_de_chile (supuesto del orquestador).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
E="$1"; F="$2"; S="$3"; shift 3
R=evaluacion/registro; D=evaluacion/datos
CFG="KERNA_COLECCION=normativa_cl_x_e KERNA_ENR_BM25=concat KERNA_EVALUADOR=1 KERNA_EVALUADOR_VARIANTE=3m KERNA_EVALUADOR_CANDIDATOS=70 KERNA_HIBRIDA=1 KERNA_HIBRIDA_EXTRAS=15 KERNA_MULTIQUERY=1 KERNA_MULTIQUERY_MAX=3 KERNA_MULTIQUERY_PESO_RELATO=2 KERNA_REVISOR=1 KERNA_CONCURRENCIA=${KERNA_CONCURRENCIA:-3} $*"
declare -A EXTRA=( [prueba2]="--extra-casos $D/denuncias_nuevas_20261112.json" [prueba3]="--extra-casos $D/denuncias_sinteticas_20261113_prueba3.json" )
out="$R/casos_exp2_${E}_${S}_$F.json"
SC=""; [ "$S" = prueba3 ] && SC="KERNA_REVISOR_SIN_CAUSALES=hechos_fuera_de_chile"
# shellcheck disable=SC2086
operaciones/correr_evaluacion.sh $CFG $SC python3 evaluacion/correr_revisor.py --particion "$S" ${EXTRA[$S]:-} --salida "$out"
for pasada in 1 2 3; do
  n=$(python3 -c "import json;print(sum(x['motivo_revision'] in ('cadena_agotada','tiempo_agotado') for x in json.load(open('$out'))))")
  [ "$n" = 0 ] && break
  echo "$S: $n casos con cadena agotada; reanudando (pasada $pasada)"; sleep 60
  # shellcheck disable=SC2086
  operaciones/correr_evaluacion.sh $CFG $SC python3 evaluacion/correr_revisor.py --particion "$S" ${EXTRA[$S]:-} --reanudar "$out" --salida "$out"
done
echo "FIN $out"
