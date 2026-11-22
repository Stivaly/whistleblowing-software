# kerna_comun

Paquete Python compartido por el núcleo de Kerna AI y el Conector Veridy (`PYTHONPATH=kerna/comun`). Contiene:

- `kerna_comun/anonimizador.py`: anonimizador por reglas.
- `kerna_comun/notas.py`: objetos de las notas internas de Veridy (ver `kerna/docs/contratos.md`).
- `kerna_comun/telemetria.py`: registro de telemetría por solicitud.

## Anonimizador

`anonimizar(texto) -> Resultado` (`texto`, `conteos`) sustituye identificadores por marcadores numerados por valor
distinto: `[PERSONA_n]`, `[RUT_n]`, `[CORREO_n]`, `[TELEFONO_n]`, `[DIRECCION_n]`, `[PATENTE_n]`, `[CUENTA_n]`,
`[URL_n]`. `conteos` es tipo a cantidad de valores distintos, nunca los valores. Solo usa reglas y la biblioteca
estándar; es determinista e idempotente (los marcadores ya presentes no se tocan ni se renumeran; los valores nuevos
siguen la numeración). Solo sustituye: nunca interpreta el texto, así que instrucciones incrustadas no tienen efecto.

`contiene_identificadores(texto, identificadores) -> list[str]` devuelve cuáles de los identificadores siguen en el
texto (insensible a mayúsculas, tildes, puntos y espacios entre dígitos; coincide por palabra completa). Es para pruebas
de fuga.

### Qué detecta

| Tipo | Reglas |
|---|---|
| RUT | Con puntos y guion; con guion, pegado (`123456785`), con espacios (`12 345 678 5`) o mixto, validando el dígito verificador (módulo 11); cualquier formato tras `RUT`, `RUN`, `cédula`, `C.I.`, `DNI` (también `mi rut es …`). |
| CORREO | Dirección con `@`, insensible a mayúsculas. |
| TELEFONO | Móviles (`+56 9 1234 5678`, `912345678`, con guiones/puntos/espacios), fijos de Santiago (`2`) y regionales (`32`-`75`) con o sin `+56`, internacionales `+CC …` (8 a 15 dígitos). `+56 9 …` y `9…` son el mismo valor. |
| URL | `http(s)://`, `www.` y dominios con `.cl/.com/.net/.org/.io/.info/.edu/.gob/.gov`. |
| PERSONA | Tras tratamiento, cargo o frase de contexto; secuencias de 2 a 5 palabras con mayúscula; un nombre o apellido suelto de los diccionarios (Registro Civil de Chile, España, Argentina y otros países), también en minúscula o mal escrito (`karlos`, `frnando`), sin tomar palabras del español, comunas ni tribunales. Unifica variantes de una misma persona. |
| DIRECCION | Palabra clave (`calle`, `avenida`, `Gran Avenida`, `pasaje`…) + nombre + número, tras `domicilio:`/`dirección es`, o un nombre de calle de Chile (OpenStreetMap) + número (`vivo en los aromos 123`). |
| PATENTE | `AA-BB-12`, `BBBB-12` (cuatro consonantes), con o sin guion o espacio; formato antiguo `AB-1234` solo tras `patente`/`placa`. |
| CUENTA | Números tras `cuenta`, `cta`, `tarjeta`, `iban` (6 o más dígitos), tarjetas `4-4-4-4` y 13 a 19 dígitos que cumplan Luhn. |

No toca: leyes y artículos (`Ley N.° 21.643`, `Ley Karin`, `Código del Trabajo`, `artículo 211-A`), instituciones y
siglas (Dirección/Inspección del Trabajo, Ministerio Público, Fiscalía, CMF, SII, Contraloría, Agencia de Protección de
Datos Personales…), montos, fechas, ni la primera palabra de una oración solo por llevar mayúscula.

### Límites conocidos y detalle

Ver `kerna/docs/anonimizador.md`: cómo funciona cada regla, de dónde salen los diccionarios (`kerna_comun/diccionarios/`,
fuentes y licencias en `FUENTES.md`), qué oculta de más y qué no detecta.

### Cómo ampliar las reglas

- Excepciones (leyes, instituciones, siglas, meses, razones sociales): `EXCEPCIONES_PALABRAS` (palabras sueltas) y
  `EXCEPCIONES_FRASES` (varias palabras), en minúsculas y sin tildes.
- Tratamientos y cargos que preceden a un nombre: `TRATAMIENTOS`. Disparadores de contexto: `_DISPARADORES`.
- Nombres, apellidos, calles, lugares y lemario: se regeneran desde sus fuentes con `kerna/comun/herramientas/generar_diccionarios.py`
  (no se editan a mano). Palabras que abren oración: `INICIOS_DE_ORACION`.
- Comunas que acompañan una dirección: `COMUNAS`.
- Reglas con expresión regular: tabla `_REGLAS` (tipo, expresión, grupo, validador, función de clave); el orden es la
  prioridad, y una regla no toca lo que una anterior ya asignó.
- Toda regla nueva se prueba añadiendo casos a `kerna/pruebas/datos/anonimizador_casos.json` (texto, `debe_desaparecer`,
  `debe_conservarse`) y se ejecuta con `cd kerna && /usr/bin/python3 -m pytest pruebas/unitarias/test_anonimizador.py -q`.
