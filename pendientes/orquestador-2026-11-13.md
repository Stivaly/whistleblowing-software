# Encargo del orquestador (Opus), 2026-11-13 desde las 10:30, 12 horas sin la usuaria

Eres el orquestador. No editas código tú mismo: encargas a agentes **Sonnet 5.5 de esfuerzo medio** (Agent con `model: sonnet`, `effort: medium`), **siempre en primer plano** (`run_in_background: false`). **Tú eres el auditor y el responsable** de verificar todo lo que entregue Sonnet: capturas imagen por imagen, datos leídos de verdad, cifras comprobadas. Revisar por encima no cuenta como auditar.

Orden: **Parte A primero (todo), después Parte B, única y exclusivamente, hasta lograr la meta.** No pares mientras quede algo que se pueda hacer sin la usuaria. Si de verdad ya no queda nada, tienes autorización para detener el bucle de Continuo (escribe `[CONTINUO:TERMINADO]`).

## Autonomía (dicho por la usuaria)
- Cuando la usuaria ya dio una instrucción clara, se ejecuta con criterio propio. **No le mandes listas para aprobar ni le preguntes lo ya decidido.** Pregunta solo lo que de verdad no esté definido; si no, aplica un supuesto razonable y anótalo.
- Texto: **menos, no más.** Nombres que se entiendan solos y «?» de una línea. Ningún cambio debe agregar frases.

## Reglas para cada agente (inclúyelas en cada encargo)
- **Relevo:** máximo 300.000 tokens; hacia ~250.000 cierra, prueba, commitea, anota lo que falta (en orden, archivo y línea) y entrega. Luego agente nuevo, nunca retomar uno viejo.
- **Despliegue del front:** solo `kerna/front/desplegar.sh --ref HEAD` con las pruebas pasando. Anotar antes el último commit bueno; si `/salud` falla o hay vistas rotas, volver con `--ref <bueno>`.
- **Capturas:** reales de producción a 390, 1366 y 1920 px, **en Chromium y también en Firefox** (y WebKit si se puede) con el contenedor Playwright.
- **Archivos:** nunca eliminar archivos del repo; mover a `.papelera/AAAA-MM-DD/<ruta>` y anotar en `pendientes/eliminaciones-pendientes.md`. (Excepción autorizada: punto A6, casos de Veridy.)
- **Rama:** solo `feature/kerna-pipeline-azure`. `git add` con rutas explícitas, nunca `-A` ni `.`.
- **Terraform:** `echo n | infra/aplicar.sh veridy|kerna` y luego `-y` si solo crea o reemplaza el grupo de contenedores o agrega recursos nuevos. Nunca destruir PostgreSQL, almacenamiento con datos, certificados ni Key Vault.
- **Rendimiento:** TTFB < 100 ms en caliente, CPU en reposo < 1 %; animar solo `transform`/`opacity`, sin `steps()`.
- **Contraste AA** (`kerna/diseno/identidad-v3/calcular_contraste_v3.py`); lima, amarillo y cian nunca como texto sobre claro.
- **Veridy:** autorizado a encenderlo (`infra/veridy/veridy.sh encender`) cuando el trabajo lo necesite (A5, A6, A8, Parte B).
- **Modelos:** ninguno corre en el host; por API o jobs de Azure. Nunca registrar ni persistir texto de denuncias.

## Índice de scripts de operación (usar SIEMPRE estos; nunca az/curl/docker sueltos ni ver claves)
Si falta uno, crear un script de función fija en `kerna/operaciones/`, commitearlo y agregarlo aquí.

| Para qué | Script |
|---|---|
| Desplegar el front | `kerna/front/desplegar.sh --ref HEAD` (corre las pruebas antes; para volver atrás: `--ref <commit bueno>`) |
| Construir y subir la imagen del conector, núcleo o servicio local | `infra/scripts/subir_imagen_kerna.sh conector --tag <tag>` |
| Construir y subir la imagen de Veridy | `infra/veridy/subir_imagen.sh --tag <tag>` |
| Terraform, por ejemplo para desplegar el conector cambiando `conector_tag` | `echo n \| infra/aplicar.sh veridy\|kerna` (ver el plan) · `infra/aplicar.sh veridy\|kerna -y` (aplicar) |
| Encender, apagar o ver el estado y los registros de Veridy y del conector | `infra/veridy/veridy.sh encender \| apagar \| estado \| logs [contenedor]` |
| Telemetría (solo lectura y conteos) | `kerna/operaciones/telemetria.sh resumen \| reprocesos \| motivos [días]` · `telemetria.sh kql <archivo\|"consulta"> [días]` |
| Tablas de Azure | `kerna/operaciones/tablas.sh ver <tabla> ["filtro"] \| solicitud \| ajustes` · escribir: `CONFIRMAR=si kerna/operaciones/tablas.sh escribir <tabla> <PK> <RK> campo=valor…` |
| Probar el front en producción | `kerna/operaciones/probar_front.sh [--clave-anterior] [--reintento]` (código 1 si algo falla) |
| Cargar denuncias en Veridy | `kerna/operaciones/cargar_denuncias.sh [N] [--dry-run \| --verificar \| --casos …]` (idempotente; código 3 = límite por hora, repetir después) |
| Borrar de Veridy los casos que Kerna no puede procesar (sin acceso, sin texto, ilegibles; sin `--aplicar` solo cuenta; tope 10 salvo `--max`) | `kerna/operaciones/borrar_casos_invalidos.sh [--aplicar] [--max N]` |
| Crear la cuenta `kerna-e2e` de Veridy (destinatario sin permisos extra; clave en Key Vault `veridy-kerna-e2e-password`, nunca impresa; verifica el inicio de sesión; idempotente) | `kerna/operaciones/crear_cuenta_e2e.sh` |
| Ejecutar un script de Python dentro del contenedor de Veridy (base de los dos anteriores; se carga con `source`) | `kerna/operaciones/_veridy_remoto.sh` (`remoto_py archivo.py`) |
| Historial del ping al front (Logic App cada 15 min) | `kerna/operaciones/ping_front.sh [N]` |
| Despertar o reiniciar el front antes de medir | `kerna/operaciones/despertar_front.sh [--reiniciar]` |
| Navegador | `kerna/operaciones/playwright.sh pdf \| modal [--confirmar] \| script <archivo.py>` |
| Capturas y mediciones de vistas | `kerna/front/herramientas/medir_vistas.sh` |
| Verificar el botón de reintento (captura en curso y al terminar, tras `probar_front.sh --reintento`) | `kerna/operaciones/playwright.sh script kerna/operaciones/capturar_reintento.py` |
| Medir la portada (alto, huecos, desborde) | `kerna/operaciones/playwright.sh script kerna/operaciones/medir_portada.py` |
| Prueba de íconos y logos (falla si uno ocupa espacio y no pinta píxeles; portada y panel, 390/1366/1920 px) | `kerna/operaciones/probar_iconos.sh [anchos...]` |
| Prueba de movimiento y CPU en reposo (órbitas, satélites, arco, teclado, botón de reintento, «En vivo»; solo lectura) | `kerna/operaciones/probar_movimiento.sh` |
| Íconos, estáticos y rasterizados | `kerna/front/herramientas/{construir_identidad,construir_estaticos,construir_echarts,lamina_iconos,rasterizar_baldosas,rasterizar_decoracion}` |
| Limpiar Docker (imágenes y caché, nunca volúmenes) | `infra/limpiar_docker.sh` |

## Parte A: lo que pidió la usuaria (2026-11-13, 09:30)

Estado de partida: front `e1e38e947` desplegado, conector `0e75d50c8` desplegado. Diseño de bandas tintadas, ancho 1.440 px y movimiento: aprobados («mucho mejor»), pero fallan los detalles.

**A1. Íconos y logos invisibles en Firefox (prioridad alta).** En Firefox para Android no se ve casi ningún ícono, aunque su espacio está reservado:
- Informe: botones Otro período, PDF, Excel, CSV; baldosa del veredicto; cuadrados vacíos en la banda de indicadores; íconos de ley sobre los anillos.
- Resumen: íconos de los indicadores y de las leyes.
- Ajustes: íconos de cada sección.
Hallar la causa real (probable: sprites externos con `<use href="archivo.svg#id">`, `symbol` o `mask` que Firefox no resuelve igual). Ampliar `kerna/operaciones/probar_iconos.sh` para que corra **también en Firefox y WebKit**; debe fallar hoy y pasar después del arreglo. Las pruebas anteriores solo usaban Chromium: por eso dieron 0 fallos.

**A2. Ajustes en móvil.** La barra fija «N cambios sin guardar · Descartar · Guardar» tapa la última fila («Avisar sin sugerencia tras») y no deja bajar más: reservar espacio abajo mientras está visible. Los botones Descartar y Guardar se ven desalineados (texto corrido a la derecha). En «Compartir con» aparece una barra lima y azul a la izquierda que parece un error.

**A3. «Acierto por ley» (Resumen e Informe) no debe ocupar todo el ancho.** Hoy son tres anillos y una línea suelta a la derecha («329 artículos sugeridos sin ley identificada…»). Que la banda mida lo que su contenido pide y comparta fila con otra banda, o se compacte; quitar o reubicar esa línea. Criterio: ninguna banda estirada para mostrar poco.

**A4. Menos texto en todo el front.** Se agregaron frases largas cuando se pidió lo contrario. Ejemplos a reducir: titular de 3 líneas «En 7 días, 30 % recibió sugerencia. Según la telemetría, 205 casos esperan reintento.»; «Estimado · En espera · Próximo reintento…»; «Pasó a revisión manual»; «Sugerencias útiles según auditores»; «Ganancia a 5 años, valor de hoy»; «329 artículos sugeridos sin ley…». Nombres cortos que se entiendan solos; «?» de una línea.

**A5. El Resumen nunca debe volver a la cifra inflada.** Hoy, si el estado del conector tiene más de 5 minutos (pasa siempre que el vigía apaga Veridy), el Resumen vuelve a la estimación de telemetría (205; 202/98/3). Mostrar siempre el **último estado real conocido** del conector (con su hora en el «?»), nunca la estimación inflada.

**A6. Reintentar TODOS los casos sin sugerencia y borrar de Veridy los que no sirven.** La usuaria pidió reintentar todas las denuncias sin sugerencia; quedaron sin hacerse. Con Veridy encendido:
1. Obtener la lista real de casos de Veridy sin sugerencia y reintentarlos todos.
2. Los que siguen sin sugerencia porque están mal hechos (no pueden generarla): **borrarlos de Veridy directamente.** Autorización explícita de la usuaria: no hay que mostrarle la lista ni pedir confirmación; no se pierde ningún dato útil. Hacerlo con un script de función fija en `kerna/operaciones/` (que registre cuántos y por qué, sin texto de denuncias).
3. Verificar en el Resumen y en la telemetría que ya no quedan pendientes falsos. Registrar en `kerna/evaluacion/registro-pruebas.md`.

**A7. No subir el plan del front: ping cada 15 minutos.** Crear algo liviano y barato en Azure (Azure Function con temporizador, Container Apps Job o Logic App, lo más barato) que visite la página del front cada 15 minutos para que el plan F1 no se duerma. Terraform en `infra/` (Kerna), aplicado con `infra/aplicar.sh kerna`. Verificar que la primera visita deja de ser lenta.

**A8. Cuenta `kerna-e2e`.** Encender Veridy y crear la cuenta tú (no la usuaria), guardando la clave en Key Vault mediante un script; nunca imprimirla.

**A9. Denuncias sintéticas: auditoría real.** `kerna/evaluacion/datos/denuncias_sinteticas_20261113.json` (150 relatos) **no fue auditado**. Revísalos tú, todos: realistas y específicos, sin plantillas ni patrones repetidos, variedad real de tema, tono y extensión, ~15 % ambiguos y ~10 % sin falta, datos personales ficticios y variados, sin textos copiados. Los que no cumplan se reemplazan con un agente nuevo (el encargo **no puede revelar el contexto**: ni modelo, ni evaluación, ni leyes, ni país) y se vuelven a auditar. Resguardar el resultado como archivo nuevo en `kerna/evaluacion/datos/` (fuera de git) sin modificar los existentes, y registrar la auditoría en `kerna/evaluacion/registro-pruebas.md`.

**A10. Ya decidido, no tocar:** UF en el valor actual (40.000); no subir a B1.

Auditoría de la Parte A: capturas a 390/1366/1920 en Chromium **y Firefox**; ninguna banda estirada para poco contenido; nada de texto agregado; íconos visibles en ambos navegadores.

## Parte B: evaluación continua y mejora de modelos (después de la Parte A)

Leer antes `pendientes/relevo-revisor-y-evaluacion-2026-11-12.md` (estado, sets, comandos, mediciones, siguientes pasos) y `pendientes/revisor-juridico-kerna.md`. Meta **obligatoria**: **recall@5 por artículo ≥ 0,80** (si no se cumple, no le aceptan el proyecto). Latencia no bloquea.

1. **Etiquetar las sintéticas auditadas (A9)** como set aparte `prueba3` (vía `--extra-casos`, sin mezclar con desarrollo), con un agente que etiquete leyes y artículos del corpus y marque controles; tú auditas las etiquetas (muestra amplia, no por encima). Cargarlas en Veridy solo si la evaluación lo necesita.
2. **Medir todo** con etiquetas corregidas y corpus 181: retriever solo y cadena completa (evaluador + híbrida + revisor, mejor configuración del relevo §2) en desarrollo, prueba, prueba2 y prueba3. Registrar cada medición (fecha, commit, comando, parámetros, resultado) en `kerna/evaluacion/registro-pruebas.md` y `kerna/evaluacion/registro/`.
3. **Mejorar hasta ≥ 0,80**, en el orden del relevo §6: orden del evaluador (palanca principal; hit@70 ≈ 0,97), 20.393 (artículos de procedimiento sobre 1, 3, 4), partir arts. 82/84 por letra, criterios del revisor, más casos de desarrollo para ajustar. Cada cambio se mide en desarrollo y se confirma una vez en los sets de prueba (sin sobreajustar; los criterios del revisor se escriben sin mirar los casos de evaluación).
4. **Investigar en fuentes serias** (papers de arXiv/ACL/SIGIR, documentación oficial de modelos y rerankers, benchmarks de recuperación jurídica como LegalBench-RAG, COLIEE, LePaRD), no cualquier página, qué más subiría el recall: rerankers cruzados, fine-tuning de embeddings con pares sintéticos, HyDE/expansión de consulta, descomposición por conductas, recuperación jerárquica ley→artículo, etiquetado de artículos con conductas, etc. Anotar fuentes y conclusión en `kerna/evaluacion/investigacion-recall.md` y probar las más prometedoras.
5. Lo del núcleo lo hacen agentes Sonnet con estas reglas; despliegues del núcleo con los scripts del índice.
6. Llevar los campos del revisor a la nota de Veridy cuando la cadena esté estable.

## Al terminar o cada ~3 horas
Actualizar `pendientes/resumen-sesion-2026-11-12.md` (sección «Orquestador 2026-11-13, tanda de 12 h»): qué quedó, qué auditaste (rutas de capturas y archivos), mediciones de recall con fecha y commit, qué falta. Commitear solo tus archivos.
