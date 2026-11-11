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
| RUT | Con puntos y guion (`12.345.678-5`); con guion sin puntos (se valida el dígito verificador); sin guion solo tras `RUT`, `RUN`, `cédula`, `C.I.`. Misma clave sin importar puntos ni `k`/`K`. |
| CORREO | Dirección con `@`, insensible a mayúsculas. |
| TELEFONO | Móviles (`+56 9 1234 5678`, `912345678`, con guiones/puntos/espacios), fijos de Santiago (`2`) y regionales (`32`-`75`) con o sin `+56`, internacionales `+CC …` (8 a 15 dígitos). `+56 9 …` y `9…` son el mismo valor. |
| URL | `http(s)://`, `www.` y dominios con `.cl/.com/.net/.org/.io/.info/.edu/.gob/.gov`. |
| PERSONA | Nombre propio tras tratamiento o cargo (`don`, `doña`, `señor/a`, `sr.`, `jefe/a`, `gerente`, `supervisor/a`, `compañero/a`, `colega`, `trabajador/a`, `denunciado/a`…, ver `TRATAMIENTOS`), tras `me llamo`, `mi nombre es`, `denuncio a`, etc., y toda secuencia de 2 a 5 palabras con mayúscula inicial (incluye `de`, `del`, `de la`, `de los`, `de las`). Luego se unifican variantes: `María Pérez` y `María Pérez Soto` comparten marcador; `maria perez` en minúsculas y apariciones sueltas de un nombre o apellido que identifica a una sola persona ya detectada reciben el mismo marcador. Al inicio de oración se descarta la primera palabra si es de `INICIOS_DE_ORACION` o si la siguiente es un nombre de pila conocido (`NOMBRES_CONOCIDOS`). |
| DIRECCION | `calle/avenida/av./pasaje/camino/población/villa/condominio/parcela` + nombre con mayúscula + número, con `depto/oficina/casa/block/torre/piso` y comuna si acompañan; también tras `domicilio:`/`dirección es`. |
| PATENTE | `AA-BB-12`, `BBBB-12` (cuatro consonantes), con o sin guion o espacio; formato antiguo `AB-1234` solo tras `patente`/`placa`. |
| CUENTA | Números tras `cuenta`, `cta`, `tarjeta`, `iban` (6 o más dígitos), tarjetas `4-4-4-4` y 13 a 19 dígitos que cumplan Luhn. |

No toca: leyes y artículos (`Ley N.° 21.643`, `Ley Karin`, `Código del Trabajo`, `artículo 211-A`), instituciones y
siglas (Dirección/Inspección del Trabajo, Ministerio Público, Fiscalía, CMF, SII, Contraloría, Agencia de Protección de
Datos Personales…), montos, fechas, ni la primera palabra de una oración solo por llevar mayúscula.

### Límites conocidos

Una heurística de nombres no es infalible. No cubre o falla en:

- Nombres sin mayúscula inicial o en mayúsculas sostenidas sin contexto (`pedro soto` solo se detecta si ya apareció
  bien escrito antes; `PEDRO SOTO` solo si lleva un nombre de pila de `NOMBRES_CONOCIDOS` o tratamiento).
- Un nombre suelto sin tratamiento, disparador ni segunda palabra (`Ayer Xiomara me gritó`; `Pérez lo hizo`) si no hay una mención completa previa.
- Apodos, iniciales (`P. Soto` solo detecta `Soto` con tratamiento) y nombres escritos con errores.
- Falsos positivos: dos palabras con mayúscula que no son personas ni están en las excepciones (títulos en Title Case
  como `Informe Final`, nombres de empresas como `Asesorías Quilmahue`, productos, lugares no listados). Se prefiere
  sobre-anonimizar a filtrar.
- Calles escritas en minúscula, sin número, o sin palabra clave (`vivo por Los Olmos 10`); barrios, referencias
  (`frente al supermercado`) y nombres de empresas, cargos o lugares que identifican indirectamente.
- RUT sin guion ni contexto (`134567895`), teléfonos de 8 dígitos sin código de área, números de cuenta sin la palabra
  `cuenta`/`tarjeta` cerca y menos de 13 dígitos, patentes antiguas sin la palabra `patente`.
- Identificación por combinación de datos (cargo + fecha + lugar), datos en imágenes y texto con espacios intercalados o
  ofuscado (`ana arroba correo punto cl`).
- Un nombre con tratamiento detectado como nombre completo se aliasa por nombre y apellido sueltos: si dos personas
  comparten un nombre, la aparición suelta no se sustituye.

### Cómo ampliar las reglas

- Excepciones (leyes, instituciones, siglas, meses, razones sociales): `EXCEPCIONES_PALABRAS` (palabras sueltas) y
  `EXCEPCIONES_FRASES` (varias palabras), en minúsculas y sin tildes.
- Tratamientos y cargos que preceden a un nombre: `TRATAMIENTOS`. Disparadores de contexto: `_DISPARADORES`.
- Nombres de pila (desambiguan el inicio de oración): `NOMBRES_CONOCIDOS`; palabras que abren oración: `INICIOS_DE_ORACION`.
- Comunas que acompañan una dirección: `COMUNAS`.
- Reglas con expresión regular: tabla `_REGLAS` (tipo, expresión, grupo, validador, función de clave); el orden es la
  prioridad, y una regla no toca lo que una anterior ya asignó.
- Toda regla nueva se prueba añadiendo casos a `kerna/pruebas/datos/anonimizador_casos.json` (texto, `debe_desaparecer`,
  `debe_conservarse`) y se ejecuta con `cd kerna && /usr/bin/python3 -m pytest pruebas/unitarias/test_anonimizador.py -q`.
