# Relevo: revisor jurídico, búsqueda híbrida, sets de evaluación y vigía de Veridy

Estado al 2026-11-12 (último commit de esta línea: `ad7ac39be`, rama `feature/kerna-pipeline-azure`).
Retomar **después** de que existan las denuncias sintéticas que está generando la usuaria/otro agente
(ver `cc65df90a`: las sintéticas solo se generan, no se cargan ni se prueban hasta nuevo aviso).

## Reglas que aplican a quien siga

- Commitear **solo los archivos que tú toques**, con rutas explícitas en `git add` (nunca `git add -A`/`.`); otras
  sesiones trabajan en el mismo árbol (front, orquestador). En archivos compartidos (`registro-pruebas.md`,
  `registro/*.jsonl`, `pendientes/*.md`) revisar `git diff` antes de agregar.
- Nunca borrar: mover a `.papelera/AAAA-MM-DD/<ruta>` y anotar en `pendientes/eliminaciones-pendientes.md`.
- Toda medición se registra en `kerna/evaluacion/registro-pruebas.md` y `kerna/evaluacion/registro/` (fecha, commit,
  comando, parámetros, resultado). Mediciones de **tiempos**: visita de calentamiento previa descartada (el front F1
  duerme a los 20 min; el núcleo escala a cero; Veridy se apaga a los 60 min).
- Modelo por defecto `gpt-5-nano`; `gpt-5-mini` solo si una medición lo justifica. Nunca enviar el corpus completo
  al LLM. Nunca registrar ni persistir texto de denuncias.
- Sesgo: los criterios del revisor se escriben sin mirar los casos de evaluación.
- Cambios de Terraform: `echo n | infra/aplicar.sh <x>` para ver el plan; si reemplaza o destruye, consultar a la usuaria.

## 1. Revisor jurídico (paso 5b)

Diseño completo y decisiones: `pendientes/revisor-juridico-kerna.md` (§1 por qué tercer agente, §3 especificación,
§4 brechas RAG, §5 método de medición, §7 resultados, §8 decisiones de casos dudosos).

- Código: `kerna/nucleo/kerna_nucleo/revisor/agente.py` y `revisor/criterios/{transversal,ley_karin,ley_20393,
  datos_personales}.md` (se cargan solo las familias de los artículos en juego). Integración en `orquestador.py`
  (`_revisar`, entre el generador y el validador). Flag `KERNA_REVISOR=1` (apagado por defecto).
- Dictamen por artículo: confirma / condiciona / veta. Veto solo con causal cerrada (régimen, sujeto, vigencia,
  naturaleza, territorio) y hecho válido; si no, el código lo baja a condiciona. La confianza solo baja.
- La "ley nueva de datos" (21.719) está en el corpus como texto reformado de la 19.628 (87 fragmentos, vigencia
  2026-12-01); el revisor la trata como familia `datos`. Antes del 1-dic condiciona por vigencia, no veta.
- Resultado (desarrollo / prueba): no baja el recall (0,500→0,500; 0,462→0,462), 0 vetos incorrectos, pero condiciona
  el 86 % y casi no limpia los controles. **Pendiente:** afinar criterios para que confirme cuando corresponde.
- Decisiones: DEN-0098 → veto a 18.575 art. 14 es correcto; DEN-0110 → sigue como control.
- **Pendiente:** los campos del revisor (`dictamen`, `causal_veto`, `condiciones`, `alertas_revision`...) aún no
  llegan a la nota `kerna_sugerencia` de Veridy. Contrato en `kerna/docs/contratos.md`.
- **Pendiente:** `fecha_hechos` no existe como campo estructurado (decisión de producto).

## 2. Búsqueda híbrida y conductas del perfil

- `kerna_nucleo/bm25.py`, `retriever.py`, `proveedores/qdrant.py`, `proveedores/voyage.py`, `evaluador_ids.py`
  (`extraer_perfil`, variante `3m`). Flags apagados por defecto.
- Mejor configuración: `KERNA_EVALUADOR=1 KERNA_EVALUADOR_VARIANTE=3m KERNA_HIBRIDA=1 KERNA_HIBRIDA_EXTRAS=15
  KERNA_MULTIQUERY=1 KERNA_MULTIQUERY_MAX=3 KERNA_MULTIQUERY_PESO_RELATO=2`.
- Con evaluador: desarrollo 0,50→0,56; prueba 0,455→0,64 (IC solapados). hit@70 ≈ 0,97: **el cuello de botella es
  el orden del evaluador**, no traer más candidatos.

## 3. Corpus

- Se agregaron los artículos de definición de acoso y prescripción de los estatutos: `236392-karin-art-84/158/159`
  (18.834) y `30256-karin-art-82/154/155` (18.883). Opción nueva `articulos_incluir` en
  `kerna/pipeline_bcn/extraer_bcn.py` y `leyes.json`. Corpus: 181 artículos, `version_corpus` 3.
- **Pendiente:** los arts. 82 y 84 son listas de 13 prohibiciones y nunca entran al top-10 (embedding diluido).
  Propuesta: partirlos por letra (cambia la unidad de fragmento; decidir y medir).

## 4. Sets de evaluación

| Set | Archivo (fuera de git) | Uso | Casos medibles |
|---|---|---|---|
| desarrollo | `kerna/evaluacion/datos/triage_casos.json` (jurídicos) | ajustar | 42 + 8 controles |
| prueba | mismo archivo (Reddit) | medir una vez | 13–15 + 16 controles |
| prueba2 | `kerna/evaluacion/datos/denuncias_nuevas_20261112.json` (NUE-0001..0062) | medir | 48 + 14 controles |

- Triage y correcciones de etiqueta documentados en `kerna/evaluacion/triage-casos.md` (`articulos_corregidos`
  conserva las originales en `articulos_corpus`; usar `--etiqueta corregida`).
- prueba2: 47 de Reddit (vía Arctic Shift) + 15 fallos/DT/noticias; 14 casos de confianza baja y 7 controles
  discutibles (lista en el informe del agente, resumida en `por_que_frontera`/`justificacion_juridica` de cada
  caso). **Pendiente:** revisión de etiquetas por el equipo.
- Las denuncias sintéticas nuevas deben entrar como set aparte (p. ej. `prueba3` vía `--extra-casos`), sin
  mezclarse con desarrollo.

## 5. Mediciones vigentes (recall@5 por artículo)

| Medición | desarrollo | prueba | prueba2 |
|---|---|---|---|
| Retriever solo, etiqueta corregida | 0,548 | 0,467 | 0,562 |
| Cadena con evaluador + híbrida (mejor config) | 0,559* | 0,636* | sin medir |
| + revisor (hit@5 antes→después) | 0,500→0,500 | 0,462→0,462 | sin medir |

\* medido antes de corregir etiquetas y ampliar corpus; repetir.
prueba2 por ley: Karin 0,69, datos 0,43, **20.393 0,20** (trae arts. de procedimiento 13, 17 ter, 20, 22 en vez de 1, 3, 4).

Comandos:
- Retriever: `python3 kerna/evaluacion/recall_retriever.py --triage kerna/evaluacion/datos/triage_casos.json
  --etiqueta corregida --particion desarrollo|prueba` y `--extra-casos <json> --particion prueba2`.
- Cadena + revisor: `kerna/evaluacion/correr_revisor.py` (con los flags de §2 y `KERNA_REVISOR=1`; `--reanudar`
  repite casos con cadena agotada por 429). Métricas: `medir_revisor.py`. Híbrida: `medir_hibrida.py`.
- Suite: `python3 -m pytest -q` desde `kerna/` (388; `test_conector_reconciliacion` falla a ratos, preexistente).

## 6. Siguientes pasos, en orden

1. Medir con las sintéticas (set aparte) y repetir la cadena completa + revisor en desarrollo, prueba y prueba2 con
   etiquetas corregidas y corpus 181.
2. Atacar el orden del evaluador (palanca principal hacia 0,80).
3. Resolver 20.393 (artículos de procedimiento por encima de 1, 3, 4) y partir arts. 82/84 por letra; medir.
4. Afinar criterios del revisor para confirmar más y limpiar controles.
5. Llevar los campos del revisor a la nota de Veridy.
6. Repetir las 6 capturas de TTFB del front con calentamiento; `kerna/front/herramientas/medir_vistas.py` debe
   guardar hora por pedido (`kerna/evaluacion/depurar_arranque_frio.py` ya aplica la regla).

## 7. Vigía de Veridy (bloqueado: espera decisión de la usuaria)

- Bug corregido en `infra/veridy/contenedor/vigia.py` (`bb02d6ce1`): el apagado de PostgreSQL fallaba con
  `UnsupportedMediaType` (faltaba `Content-Type: application/json`), así que solo se apagaba el contenedor.
- Regla nueva: desde **2026-11-27** PostgreSQL (y toda BD) queda siempre arriba; solo se apagan los contenedores de
  Veridy (se levantará en local). Implementado en `vigia.py` (`VERIDY_PG_SIEMPRE_DESDE`) y `veridy.sh apagar`.
- **Sin aplicar en Azure:** el plan (`echo n | infra/aplicar.sh veridy`) reemplaza `azurerm_container_group.veridy`
  (datos en PostgreSQL y Azure Files no se pierden). Se preguntó a la usuaria: aplicar ahora y apagar la base a mano,
  o dejar la base arriba hasta el 27. Al 2026-11-12 Veridy estaba `Stopped` y PostgreSQL `Ready` (cobrando).
