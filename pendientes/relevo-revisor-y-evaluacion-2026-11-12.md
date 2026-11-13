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

### Medición base B2 (2026-11-13, commit 3d6d7785e, etiqueta corregida, corpus 181, gpt-5-nano)
Configuraciones: (a) retriever solo; (b) cadena con la mejor config de §2 (+ `KERNA_EVALUADOR_CANDIDATOS=70`); (c) (b) + `KERNA_REVISOR=1`
((b) y (c) de una sola corrida: el revisor va después del generador). Casos en revisión manual cuentan como fallo. recall@5 = hit@5 por artículo.

| Set | Ley (n) | (a) retriever recall@5 [IC] | (b) cadena recall@5 [IC] | (c) +revisor [IC] |
|---|---|---|---|---|
| desarrollo | global (42) | 0.548 [0.40-0.69] | 0.429 [0.29-0.57] | 0.405 [0.26-0.55] |
| desarrollo | 19.628-21.719 (16) | 0.688 [0.44-0.88] | 0.375 [0.12-0.62] | 0.375 [0.12-0.62] |
| desarrollo | 20.393 (9) | 0.111 [0.00-0.33] | 0.222 [0.00-0.56] | 0.222 [0.00-0.56] |
| desarrollo | 21.643 (17) | 0.647 [0.41-0.88] | 0.588 [0.35-0.82] | 0.529 [0.29-0.76] |
| prueba | global (15) | 0.467 [0.20-0.73] | 0.467 [0.20-0.73] | 0.467 [0.20-0.73] |
| prueba | 19.628-21.719 (8) | 0.250 [0.00-0.62] | 0.125 [0.00-0.38] | 0.125 [0.00-0.38] |
| prueba | 21.643 (7) | 0.714 [0.43-1.00] | 0.857 [0.57-1.00] | 0.857 [0.57-1.00] |
| prueba2 | global (48) | 0.562 [0.42-0.71] | 0.688 [0.56-0.81] | 0.688 [0.56-0.81] |
| prueba2 | 19.628-21.719 (14) | 0.429 [0.21-0.71] | 0.500 [0.21-0.79] | 0.500 [0.21-0.79] |
| prueba2 | 20.393 (5) | 0.200 [0.00-0.60] | 1.000 [1.00-1.00] | 1.000 [1.00-1.00] |
| prueba2 | 21.643 (29) | 0.690 [0.52-0.86] | 0.724 [0.55-0.86] | 0.724 [0.55-0.86] |
| prueba3 | global (80) | 0.600 [0.50-0.71] | 0.688 [0.59-0.79] | 0.500 [0.39-0.61] |
| prueba3 | 19.628-21.719 (16) | 0.625 [0.38-0.88] | 0.625 [0.38-0.88] | 0.375 [0.12-0.62] |
| prueba3 | 20.393 (17) | 0.059 [0.00-0.18] | 0.471 [0.24-0.71] | 0.412 [0.18-0.65] |
| prueba3 | 21.643 (47) | 0.787 [0.66-0.89] | 0.787 [0.66-0.89] | 0.575 [0.45-0.70] |

| Set | Ley | retriever hit@5/10/20/70 | híbrida (candidatos de la cadena) hit@5/10/20/70 | evaluador top-5 |
|---|---|---|---|---|
| desarrollo | global | 0.55/0.62/0.76/0.95 | 0.57/0.64/0.79/0.98 | 0.64 |
| desarrollo | 19.628-21.719 | 0.69/0.69/0.94/1.00 | 0.75/0.88/0.94/1.00 | 0.69 |
| desarrollo | 20.393 | 0.11/0.11/0.22/0.89 | 0.00/0.00/0.22/0.89 | 0.44 |
| desarrollo | 21.643 | 0.65/0.82/0.88/0.94 | 0.71/0.76/0.94/1.00 | 0.71 |
| prueba | global | 0.47/0.60/0.87/1.00 | 0.60/0.80/0.93/1.00 | 0.47 |
| prueba | 19.628-21.719 | 0.25/0.50/0.75/1.00 | 0.25/0.62/0.88/1.00 | 0.12 |
| prueba | 21.643 | 0.71/0.71/1.00/1.00 | 1.00/1.00/1.00/1.00 | 0.86 |
| prueba2 | global | 0.56/0.71/0.77/0.94 | 0.67/0.75/0.83/1.00 | 0.77 |
| prueba2 | 19.628-21.719 | 0.43/0.50/0.50/0.79 | 0.50/0.57/0.57/1.00 | 0.50 |
| prueba2 | 20.393 | 0.20/0.40/0.80/1.00 | 0.20/0.80/1.00/1.00 | 1.00 |
| prueba2 | 21.643 | 0.69/0.86/0.90/1.00 | 0.83/0.83/0.93/1.00 | 0.86 |
| prueba3 | global | 0.60/0.74/0.82/0.99 | 0.69/0.81/0.88/0.99 | 0.84 |
| prueba3 | 19.628-21.719 | 0.62/0.75/0.81/0.94 | 0.62/0.75/0.75/0.94 | 0.75 |
| prueba3 | 20.393 | 0.06/0.12/0.41/1.00 | 0.06/0.41/0.65/1.00 | 0.47 |
| prueba3 | 21.643 | 0.79/0.96/0.98/1.00 | 0.94/0.98/1.00/1.00 | 1.00 |

Lectura (detalle y 20.393 en `kerna/evaluacion/registro-pruebas.md`, B2):
- **Traer no es el problema:** hit@70 de la híbrida 0,98-1,00 en los 4 sets (retriever denso 0,94-1,00; 20.393 de desarrollo 0,89).
- **Ordenar sí:** hit@5 de la híbrida 0,57-0,69; el evaluador sube a 0,64 / 0,47 / 0,77 / 0,84 (desarrollo, prueba, prueba2, prueba3) pero sigue lejos de 0,80 en 3 de 4.
- **El generador pierde entre 0,00 y 0,21** sobre el top-5 del evaluador (desarrollo 0,64 → 0,43; prueba3 0,84 → 0,69).
- **El revisor** no cambia desarrollo/prueba/prueba2 (-0,02 a 0,00) pero en prueba3 baja 0,69 → 0,50 (pareado -0,101, IC -0,154 a -0,054); 20 de sus vetos son `hechos_fuera_de_chile` sobre relatos sintéticos ambientados fuera de Chile y etiquetados por la norma chilena equivalente (supuesto A9 a confirmar).
- **20.393:** el retriever trae arts. de procedimiento (17 ter, 7, 8, 13, 17 bis, 20, 22, 25) en vez de 1, 3 y 4; la cadena lo sube a 0,22 / 1,00 / 0,47 (n = 9 / 5 / 17).

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

## Actualización 2026-11-13 (B1)
- prueba3 listo: `kerna/evaluacion/datos/denuncias_sinteticas_20261113_prueba3.json` (SIN-0001..SIN-0150; 80 si, 12 control, 58 no por norma fuera del corpus; 92 medibles). Comando de §5 con `--extra-casos <json> --particion prueba3`.
- Retriever solo en prueba3: global 0,600; 21.643 0,787; 19.628 0,625; 20.393 0,059. Falta: cadena completa (evaluador + híbrida + revisor) en prueba3 y repetir en los demás sets. Detalle en `kerna/evaluacion/registro-pruebas.md`.
