#!/usr/bin/env bash
# Medición del experimento de enriquecimiento: como medicion_base_b2.sh pero con colección y flags KERNA_ENR_* propios.
# Uso: kerna/operaciones/medicion_enriquecido.sh ETIQUETA AAAAMMDD "set1 set2 ..." COLECCION [VAR=valor ...]
#   ETIQUETA  nombre de la variante (salidas en kerna/evaluacion/registro/enr-<ETIQUETA>-<fecha>.json y casos_enr_<ETIQUETA>_<set>_<fecha>.json)
#   Siempre con la cadena de B2 (evaluador 3m, 70 candidatos, híbrida, multiquery) y revisor; en prueba3 el revisor no
#   aplica la causal hechos_fuera_de_chile (los relatos sintéticos ocurren fuera de Chile; supuesto del orquestador).
#   Si COLECCION termina en _p o _pe se deduplican los literales también en la medición del retriever solo.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
E="$1"; F="$2"; SETS="$3"; COL="$4"; shift 4
R=evaluacion/registro; D=evaluacion/datos
CFG="KERNA_COLECCION=$COL KERNA_EVALUADOR=1 KERNA_EVALUADOR_VARIANTE=3m KERNA_EVALUADOR_CANDIDATOS=70 KERNA_HIBRIDA=1 KERNA_HIBRIDA_EXTRAS=15 KERNA_MULTIQUERY=1 KERNA_MULTIQUERY_MAX=3 KERNA_MULTIQUERY_PESO_RELATO=2 KERNA_REVISOR=1 KERNA_CONCURRENCIA=${KERNA_CONCURRENCIA:-4} $*"
declare -A EXTRA=( [prueba2]="--extra-casos $D/denuncias_nuevas_20261112.json" [prueba3]="--extra-casos $D/denuncias_sinteticas_20261113_prueba3.json" )
args=()
for s in $SETS; do
  out="$R/casos_enr_${E}_${s}_$F.json"
  SC=""; [ "$s" = prueba3 ] && SC="KERNA_REVISOR_SIN_CAUSALES=hechos_fuera_de_chile"
  # shellcheck disable=SC2086
  operaciones/correr_evaluacion.sh $CFG $SC python3 evaluacion/correr_revisor.py --particion "$s" ${EXTRA[$s]:-} --salida "$out"
  for pasada in 1 2 3; do
    n=$(python3 -c "import json;print(sum(x['motivo_revision'] in ('cadena_agotada','tiempo_agotado') for x in json.load(open('$out'))))")
    [ "$n" = 0 ] && break
    echo "$s: $n casos con cadena agotada; reanudando (pasada $pasada)"; sleep 60
    # shellcheck disable=SC2086
    operaciones/correr_evaluacion.sh $CFG $SC python3 evaluacion/correr_revisor.py --particion "$s" ${EXTRA[$s]:-} --reanudar "$out" --salida "$out"
  done
  args+=(--set "$s=$out")
done
DD=""; case "$COL" in *_p|*_pe|*_eonly) DD="--dedup-literales";; esac
operaciones/correr_evaluacion.sh python3 evaluacion/medir_base_b2.py "${args[@]}" --coleccion "$COL" $DD --salida "$R/enr-$E-$F.json"
