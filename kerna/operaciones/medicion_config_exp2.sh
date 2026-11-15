#!/usr/bin/env bash
# Configuración fija del experimento 2 (cadena completa con revisor + completar top + reranker LLM con votos), flags explícitos.
# Uso: kerna/operaciones/medicion_config_exp2.sh ETIQUETA AAAAMMDD set [VAR=valor ...]
#   Salidas: evaluacion/registro/casos_cfg2_<ETIQUETA>_<set>_<fecha>.json (solo IDs) y cfg2-<ETIQUETA>-<set>-<fecha>.json
#   (recall@5 por artículo global y por ley con IC 95 %: evaluador, cadena, revisor). Reanuda hasta 3 veces casos con 429.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
E="$1"; F="$2"; S="$3"; shift 3
R=evaluacion/registro; D=evaluacion/datos
CFG="KERNA_COLECCION=normativa_cl_x_e KERNA_ENR_BM25=concat KERNA_EVALUADOR=1 KERNA_EVALUADOR_VARIANTE=3m KERNA_EVALUADOR_CANDIDATOS=70 \
KERNA_HIBRIDA=1 KERNA_HIBRIDA_EXTRAS=15 KERNA_MULTIQUERY=1 KERNA_MULTIQUERY_MAX=3 KERNA_MULTIQUERY_PESO_RELATO=2 KERNA_REVISOR=1 \
KERNA_GENERADOR_COMPLETAR=5 KERNA_RERANK_LLM=1 KERNA_RERANK_LLM_VENTANA=35 KERNA_RERANK_LLM_FUENTE=evaluador KERNA_RERANK_LLM_VOTO_EVAL=2 \
KERNA_RERANK_LLM_VOTO_RETRIEVER=2 KERNA_RERANK_LLM_PERMUTACIONES=2 KERNA_CONCURRENCIA=${KERNA_CONCURRENCIA:-3} $*"
declare -A EXTRA=( [prueba2]="--extra-casos $D/denuncias_nuevas_20261112.json" [prueba3]="--extra-casos $D/denuncias_sinteticas_20261113_prueba3.json" \
  [afinar]="--extra-casos $D/denuncias_complejas_20261114_etiquetadas.json" [medir_complejas]="--extra-casos $D/denuncias_complejas_20261114_etiquetadas.json" \
  [desarrollo_nuevo]="--extra-casos $D/denuncias_desarrollo_20261115_etiquetadas.json" )
out="$R/casos_cfg2_${E}_${S}_$F.json"
echo "$CFG" | sed 's/KERNA_CONCURRENCIA=[0-9]* //' > "$R/flags_cfg2_${E}_${S}_$F.txt"   # flags de la medición (sin claves)
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
operaciones/correr_evaluacion.sh python3 evaluacion/medir_base_b2.py --sets "$S" --set "$S=$out" --coleccion normativa_cl_x_e --salida "$R/cfg2-$E-$S-$F.json"
echo "FIN $out"
