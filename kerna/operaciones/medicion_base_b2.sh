#!/usr/bin/env bash
# Medición base B2: cadena (evaluador + híbrida + multiquery + revisor) en los 4 sets y luego medir_base_b2.py.
# Uso: kerna/operaciones/medicion_base_b2.sh AAAAMMDD   (salidas en kerna/evaluacion/registro/; reanuda ante 429)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
F="$1"; R=evaluacion/registro; D=evaluacion/datos
CFG="KERNA_EVALUADOR=1 KERNA_EVALUADOR_VARIANTE=3m KERNA_EVALUADOR_CANDIDATOS=70 KERNA_HIBRIDA=1 KERNA_HIBRIDA_EXTRAS=15 KERNA_MULTIQUERY=1 KERNA_MULTIQUERY_MAX=3 KERNA_MULTIQUERY_PESO_RELATO=2 KERNA_REVISOR=1 KERNA_CONCURRENCIA=${KERNA_CONCURRENCIA:-4}"
declare -A EXTRA=( [prueba2]="--extra-casos $D/denuncias_nuevas_20261112.json" [prueba3]="--extra-casos $D/denuncias_sinteticas_20261113_prueba3.json" )
args=()
for s in desarrollo prueba prueba2 prueba3; do
  out="$R/casos_b2_${s}_$F.json"
  # shellcheck disable=SC2086
  operaciones/correr_evaluacion.sh $CFG python3 evaluacion/correr_revisor.py --particion "$s" ${EXTRA[$s]:-} --salida "$out"
  for pasada in 1 2 3; do
    n=$(python3 -c "import json,sys;print(sum(x['motivo_revision'] in ('cadena_agotada','tiempo_agotado') for x in json.load(open('$out'))))")
    [ "$n" = 0 ] && break
    echo "$s: $n casos con cadena agotada; reanudando (pasada $pasada)"; sleep 60
    operaciones/correr_evaluacion.sh $CFG python3 evaluacion/correr_revisor.py --particion "$s" ${EXTRA[$s]:-} --reanudar "$out" --salida "$out"
  done
  args+=(--set "$s=$out")
done
operaciones/correr_evaluacion.sh python3 evaluacion/medir_base_b2.py "${args[@]}" --salida "$R/base-b2-$F.json"
