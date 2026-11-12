# Informe del anonimizador de Kerna (estado actual)

Medición del 2026-11-11, commit 978c760df + cambios. Código: `comun/kerna_comun/anonimizador.py` (reglas y listas, solo biblioteca estándar, sin modelo; corre en el host sin problema). Script: `evaluacion/medir_anonimizador.py`; resultado crudo en `evaluacion/registro/anonimizador_2026-11-11.json`. Entrada: `texto_original` de los 113 casos (mediana 3.411 caracteres, máximo 30.048). El informe contiene solo conteos y tipos.

## Referencia y método

- La columna `pii_en_texto` dice qué tipos de PII tiene cada caso, no cuántas apariciones ni cuáles. Por eso el recall por tipo es **por caso**: de los casos que declaran el tipo, en cuántos el anonimizador emite al menos un marcador de ese tipo. No prueba que oculte todas las apariciones dentro del caso.
- Para los tipos estructurados (correo, RUT, teléfono) se cuentan además las apariciones reales con detectores independientes sobre el texto original y el residual (recall por aparición).
- El anonimizador solo conoce 8 tipos: PERSONA, RUT, CORREO, TELEFONO, DIRECCION, PATENTE, CUENTA, URL. Los demás tipos de la referencia no tienen regla.
- `apto_triggers_anonimizador`: 57 casos "sí" y 56 "no". Los 20 casos "ninguno detectado" no se usan para recall.

## Resultados por tipo

| Tipo en `pii_en_texto` | Casos con el tipo | Casos con marcador del tipo | Recall (casos) | Apariciones (detector independiente) |
| --- | --- | --- | --- | --- |
| Correo electrónico | 3 | 3 | 1,00 | 12 de 12 ocultas |
| RUT | 1 | 1 | 1,00 | 3 de 3 ocultas (con dígito verificador válido) |
| Teléfono | 0 | - | - | 0 en los textos; los 13 marcadores TELEFONO son falsos positivos (ver abajo) |
| Nombres de personas (incluye iniciales y nombre de pila) | 27 | 24 | 0,89 | 1 nombre de pila conocido seguido de mayúscula queda sin ocultar (1 caso) |
| Dirección | 2 | 0 | 0,00 | sin regla efectiva en estos textos |
| Ubicación geográfica | 14 | 0 | 0,00 | no hay tipo para ubicación general |
| Nombres de empresas e instituciones | 60 | sin tipo | 0,00 | no se ocultan (el diseño no las cubre) |
| Cargos identificables | 33 | sin tipo | 0,00 | no se ocultan |
| Números de causa (rol, RIT, RUC) | 58 | sin tipo | 0,00 | 7 de 17 ocultas, y solo porque la regla de teléfono las confunde |
| Edad | 3 | sin tipo | 0,00 | 0 de 36 menciones ocultas ("N años", en 15 casos) |
| Salud | 4 | sin tipo | 0,00 | no se ocultan |
| Nacionalidad | 3 | sin tipo | 0,00 | no se ocultan |
| Identidad de género | 1 | sin tipo | 0,00 | no se oculta |
| Datos financieros | 1 | sin tipo | 0,00 | no se ocultan |

Marcadores emitidos en total: 780 PERSONA (79 casos), 13 TELEFONO (13 casos), 11 URL (9 casos), 3 CORREO, 2 RUT. Los 3 casos de PERSONA sin detección y el resto de la referencia de personas no se pudieron contrastar por aparición porque la referencia no las enumera.

## Huecos principales

1. **Sin cobertura por diseño**: empresas e instituciones, cargos, ubicación, edad, salud, nacionalidad, género y datos financieros. Son la mayoría de la PII declarada de la muestra (empresas 60 casos, causas 58, cargos 33). Los textos anonimizados siguen identificando por contexto.
2. **Sobre-enmascaramiento de PERSONA**: en los 86 casos que no declaran personas salen 221 marcadores PERSONA, casi todos palabras institucionales con mayúscula ("Corte [Suprema]", "Código de [Trabajo]", "[Tribunales] del Trabajo", "Servicio [Nacional]", nombres de leyes). Ese ruido degrada el texto que ve el modelo y el receptor. Hay que ampliar `EXCEPCIONES_PALABRAS` y `EXCEPCIONES_FRASES` con esos términos.
3. **Falsos positivos de TELEFONO**: los 13 marcadores (22 apariciones) son números de causa tras "N°", "rol" o "RIT" (por ejemplo 21.414-2026), no teléfonos. Ocultan el número de causa por casualidad, con el tipo equivocado, y solo cuando el formato coincide (7 de 17).
4. **Edad**: 36 menciones en 15 casos sin ocultar.
5. **Dirección**: 0 de 2 casos; las reglas de dirección y la lista de comunas no se activaron.
6. **Idempotencia**: 1 de 113 casos (DEN-0032) no es idempotente: al reanonimizar su salida aparece un marcador PERSONA nuevo en una palabra que el primer paso dejó pasar ("Enviar" tras un marcador). Es un efecto de las listas de inicio de oración, no un fallo de cifrado.

## Cómo repetir

`cd kerna && /usr/bin/python3 evaluacion/medir_anonimizador.py --json evaluacion/registro/anonimizador_AAAA-MM-DD.json`. Sin red, sin modelos.

## Carga en Veridy

Las denuncias con `texto_original` completo se cargan con `pruebas/herramientas/crear_denuncias.py --lote 113` (relato completo por defecto). Veridy admite el texto sin truncar: no hay límite de largo en el campo en la API, y el tope de 2.000 caracteres era solo de la forma resumida. Lo que limita es el ritmo: 5 envíos por hora por IP (`threshold_reports_per_hour_per_tenant_per_ip`). Registro: `evaluacion/datos/denuncias_veridy_texto_completo.json` (ignorado por git, permisos 600).
