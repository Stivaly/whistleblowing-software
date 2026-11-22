# Anonimizador de Kerna

Código: `kerna/comun/kerna_comun/anonimizador.py` y `kerna/comun/kerna_comun/nombres_cl.py`.
Diccionarios: `kerna/comun/kerna_comun/diccionarios/`. Generador: `kerna/comun/herramientas/generar_diccionarios.py`.
Pruebas: `kerna/pruebas/unitarias/test_anonimizador.py`.

## 1. Para qué sirve y dónde corre

El anonimizador reemplaza los datos que identifican a una persona por marcadores numerados antes de que el texto de una
denuncia llegue a un modelo de lenguaje:

```
Hola, soy carolina. Ayer karlos gonsales me gritó. Mi rut es 123456785 y vivo en los aromos 123.
Hola, soy [PERSONA_1]. Ayer [PERSONA_2] me gritó. Mi rut es [RUT_1] y vivo en [DIRECCION_1].
```

El mismo valor recibe siempre el mismo marcador (`María Pérez`, `maría pérez` y `Pérez` suelto, si identifica a una sola
persona, son `[PERSONA_1]`), así que el modelo puede seguir el relato sin conocer a nadie.

Corre en tres lugares, todos con el mismo código de `kerna_comun`:

| Dónde | Para qué |
|---|---|
| Conector (grupo de Veridy) | Primera pasada: anonimiza el relato antes de enviarlo al núcleo. |
| Núcleo (Container App `ca-kerna-dev-nucleo`) | Segunda pasada sobre el texto recibido, y anonimización de las observaciones de valoraciones y clasificaciones. |
| Front (pestaña «Anonimizador» de `/panel/demo`) | Demo: muestra el texto original con los datos marcados por tipo, el resultado y cuántos datos ocultó. No guarda nada. |

Principios que se mantienen desde el inicio:

- **Solo reglas y diccionarios, sin modelos.** Es determinista: el mismo texto da siempre el mismo resultado, sin costo ni
  llamadas externas.
- **Solo sustituye, nunca interpreta.** Una instrucción escondida en el relato no tiene efecto.
- **Idempotente.** Los marcadores ya presentes no se tocan ni se renumeran; los valores nuevos siguen la numeración.
- **Ante la duda, oculta.** Se prefiere ocultar de más (una marca, una frase) a dejar un dato personal a la vista.
- **`conteos` nunca lleva valores**, solo cuántos valores distintos hubo por tipo.

## 2. Cómo funcionaba antes (hasta el 2026-11-22)

Todo por reglas escritas a mano, sin diccionarios externos.

| Tipo | Cómo lo detectaba |
|---|---|
| RUT | Con puntos y guion (`12.345.678-5`); con guion sin puntos validando el dígito verificador; sin guion solo justo después de `RUT`, `RUN`, `cédula`, `C.I.`, `DNI`. |
| CORREO | Cualquier dirección con `@`. |
| TELEFONO | Móviles y fijos chilenos con o sin `+56`, con espacios, puntos o guiones; internacionales `+CC …`. |
| URL | `http(s)://`, `www.` y dominios `.cl/.com/.net/.org/.io/.info/.edu/.gob/.gov`. |
| PERSONA | Palabra con mayúscula después de un tratamiento o cargo (`don`, `señora`, `jefe`, `supervisora`, `colega`…); después de `me llamo`, `mi nombre es`, `denuncio a`; o una secuencia de 2 a 5 palabras con mayúscula (`María Pérez Soto`, `Juan de la Fuente`). Luego unificaba variantes (nombre completo, en minúscula, apellido suelto). |
| DIRECCION | Solo con palabra clave (`calle`, `avenida`, `pasaje`, `villa`…) + nombre con mayúscula + número, o tras `domicilio:` / `dirección es`. |
| PATENTE | `AA-BB-12`, `BBBB-12`; formato antiguo `AB-1234` solo tras `patente`/`placa`. |
| CUENTA | Números tras `cuenta`/`tarjeta`/`iban`, tarjetas `4-4-4-4` y números de 13 a 19 dígitos que cumplen Luhn. |

Las listas eran cortas y escritas a mano: unos 200 nombres de pila (`NOMBRES_CONOCIDOS`, solo para decidir al inicio de
una oración), 80 comunas, y listas de excepciones (leyes, instituciones, siglas, meses, cargos).

Lo que se le escapaba (documentado como límite conocido):

- **Un nombre suelto:** `carolina`, `Carolina` o `Ayer Xiomara me gritó` no se ocultaban. Un nombre necesitaba
  tratamiento, frase de contexto o un apellido al lado.
- **Nombres en minúscula** (`pedro soto`), salvo que antes hubiera aparecido bien escrito.
- **Nombres mal escritos o con otra ortografía** (`Karlos`, `Gonsales`, `Frnando`).
- **Un RUT sin guion ni contexto:** `123456785`, `12 345 678 5` o `12.345.678 5`.
- **Direcciones sin palabra clave:** `vivo en los aromos 123`, `Teatinos 950`.

Además ocultaba de más, por ejemplo tribunales y ciudades tomados por personas (`Corte de [PERSONA_1]` en
«Corte de Apelaciones de Rancagua») y comunas sueltas (`Maipú`, `Temuco`).

## 3. Qué cambió (2026-11-22)

### 3.1 Diccionarios de fuentes públicas

Ninguna lista se escribió a mano: todas se descargan de fuentes públicas y se procesan con
`generar_diccionarios.py` (minúsculas, sin tildes). Fuentes y licencias en `diccionarios/FUENTES.md`.

| Archivo | Contenido | Fuente | Entradas |
|---|---|---|---|
| `nombres.txt` | Nombres de pila frecuentes de Chile (≥ 200 inscripciones), España y Argentina | Registro Civil de Chile 1920-2021 (paquete R `guaguas`), olea/lemarios | 3.027 |
| `apellidos.txt` | Apellidos frecuentes de Chile y España | forebears.io (rangos 1-793), INE España (olea/lemarios) | 813 |
| `otros.txt` | Nombres y apellidos de otros países y los menos frecuentes de Chile (20 a 199 inscripciones) | NameDatabases (dominio público), `guaguas` | 101.524 |
| `lemario.txt.gz` | Todas las palabras y formas verbales del español | olea/lemarios | 526.303 |
| `palabras.txt` / `verbos.txt` | Nombres o apellidos que también son palabra o forma verbal (`rosa`, `paz`, `marco`, `tomas`) | cruce de las anteriores | 4.233 / 2.700 |
| `calles.txt` | Nombres de calles de Chile, sin el tipo de vía | OpenStreetMap (Overpass) | 65.835 |
| `lugares.txt` | Países y ciudades de más de 15.000 habitantes | GeoNames | 112.710 |

No se cubre todo el mundo, pero sí mucho más que lo chileno: más nombres y apellidos significan menos filtraciones.

### 3.2 Nombres

| Caso | Antes | Ahora |
|---|---|---|
| `carolina` (sola, en minúscula) | sin ocultar | `[PERSONA_1]` |
| `Ayer Carolina me dijo…` (sin apellido ni contexto) | sin ocultar | oculta |
| `hola, soy carolina` | sin ocultar | oculta |
| `Mi colega Svetlana Ivanova` | oculta (dos mayúsculas) | oculta |
| `el señor Nguyen` | oculta (tratamiento) | oculta |
| `El gerente Flores` / `que Soto la gritó` (apellido suelto) | solo con tratamiento | oculta |

Reglas:

1. Un nombre o apellido del diccionario con mayúscula, aunque esté solo, se oculta. Al inicio de una oración solo
   cuenta si no es también una palabra común (`Bueno, eso pasó` no se toca).
2. Un nombre de pila en minúscula se oculta. Si también es una palabra común (`rosa`, `luz`, `paz`, `clara`), solo se
   oculta después de `soy`, `con`, `y`, `le`, `dijo`, `me llamo`, un tratamiento, o al inicio de una oración. Si es una
   forma verbal (`marco`, `tomas`, `armando`), en minúscula nunca se toma por nombre.
3. Un nombre de otro país solo cuenta si no es una palabra del español ni un país o ciudad (`Colombia`, `Madrid` como
   lugar no se ocultan solos).
4. Comunas, tribunales y sus palabras (`Apelaciones`, `Garantía`, `Letras`, `Suprema`, `Rol`, `RIT`, `RUC`, `recurrente`,
   `demandado`…) ya no se toman por personas.

### 3.3 Nombres mal escritos o con otra ortografía

Un nombre escrito distinto también revela a la persona, así que se reconoce por parecido con los nombres y apellidos
frecuentes de Chile, España y Argentina:

- **Fonética del español de Chile:** se compara cómo suena. `c/k/qu`, `s/z/c(e,i)`, `b/v/w`, `y/ll/i`, `g/j` ante
  `e`/`i`, `h` muda y letras dobles se tratan igual. `karlos` = `carlos`, `gonsales` = `gonzalez`, `yessica` = `jessica`.
- **Un error de una letra** (que falte, sobre o cambie una), en palabras de 5 o más letras: `frnando`, `carlso`,
  `gonzalz`.
- **Salvaguarda:** nunca se aplica a una palabra del español ni a su plural, femenino o forma con pronombre (`pagos`,
  `misma`, `darle`), ni a siglas en mayúsculas (`RUT` no es `Ruth`). En minúscula, el parecido por una letra se exige
  junto a `con`, `soy`, `a`, `que`…; el fonético basta solo.

### 3.4 RUT

El dígito verificador se calcula con **módulo 11** (factores 2 a 7 desde la derecha; 11 → `0`, 10 → `K`). Ahora además
se reconoce:

| Formato | Antes | Ahora |
|---|---|---|
| `123456785` (pegado) | sin ocultar | `[RUT_1]` si el verificador cuadra |
| `12 345 678 5` (espacios) | sin ocultar | ídem |
| `12.345.678 5` (mixto) | sin ocultar | ídem |
| `mi rut es 12345678 5`, `su rut era 7654321k` | parcial | oculta |
| `el folio 123456789` (verificador no cuadra) | no | no se toca |
| `pagué 12.345.678 pesos` | no | no se toca |

Un número de 9 dígitos que empieza en 9 se trata primero como teléfono móvil.

### 3.5 Direcciones

Además de las reglas con palabra clave, se reconoce un **nombre de calle de Chile** (OpenStreetMap) seguido de un
número: `vivo en los aromos 123`, `Teatinos 950, Santiago`, `vive en Irarrázaval 3450 depto 21`. Para no confundir
números de otra cosa:

- El nombre va con mayúscula, o en minúscula tras `en`, `a` o `calle`.
- No cuenta si antes o en el nombre hay `artículo`, `ley`, `inciso`, `rol`, `folio`, `piso`, `sala`, `día`, `línea`,
  `temporada`… (`según el artículo 5`, `el día 30`, `la línea 6` no se tocan).
- Entre el nombre y el número no puede haber coma (`Santiago, 3 de mayo` no es dirección).
- `Gran Avenida` se reconoce como tipo de vía.

### 3.6 Lo que no cambió

Correos, teléfonos, URL, patentes, cuentas y tarjetas siguen con las mismas reglas. También se mantienen la
unificación de variantes de un mismo nombre, el formato de los marcadores y de `conteos`, y la API
(`anonimizar`, `anonimizar_detallado`, `contiene_identificadores`, `rut_valido`).

## 4. Límites que siguen

- **Oculta de más:** marcas y organizaciones que coinciden con un apellido (`Gmail`, `Mazda`, `Usach`) y frases como
  `con libertad` o `con soledad`, porque `Soledad` y `Libertad` son nombres frecuentes en Chile. Oculta de más, pero nunca
  deja un dato a la vista.
- `luz` en minúscula al inicio de una oración se oculta como nombre.
- Apodos (`el Chino`), iniciales (`P. S.`), nombres raros fuera de los diccionarios y escritos en minúscula, y la
  identificación por combinación de datos (cargo + fecha + lugar) no se detectan.
- Calles que no están en OpenStreetMap o sin número; referencias (`frente al supermercado`).
- Texto ofuscado (`ana arroba correo punto cl`) y datos en imágenes.

## 5. Rendimiento

- Unos 7 ms por relato (651 relatos del banco de evaluación) en este equipo.
- Los diccionarios se cargan una vez al importar el módulo (alrededor de 0,5 s).
- Pesan unos 4 MB (el lemario va comprimido).
- Solo usa la biblioteca estándar de Python.

## 6. Comprobación

- Pruebas: 124 en `test_anonimizador.py`: las 96 anteriores y 28 nuevas, 12 de lo que debe ocultar y 16 de lo que no debe
  tocar. Pasa la suite unitaria completa de Kerna (733 pruebas).
- **Comparación sobre los 651 relatos del banco** (versión anterior frente a la nueva, sin enviar nada a ningún modelo):
  - **Lo que ahora oculta:** sobre todo nombres y apellidos que antes quedaban a la vista (`Medina`, `Ivonne`, `Yeferson`,
    `Villalobos`, `Hermosilla`…).
  - **Lo que deja de ocultar:** solo comunas, tribunales y cargos (`Maipú`, `Juzgado de Garantía de Temuco`, `Congreso`).

## 7. Despliegue (2026-11-22)

| Componente | Estado |
|---|---|
| Front (demo) | Desplegado con `kerna/front/desplegar.sh --ref HEAD`; empaqueta `nombres_cl.py` y `diccionarios/`. Comprobado en pantalla. |
| Núcleo | Imagen `kerna-nucleo:3c4e84476` desplegada en `ca-kerna-dev-nucleo` (revisión 18, 100 % del tráfico); `/salud` responde y la imagen anonimiza `carolina` y el RUT pegado. |
| Conector | Imagen `kerna-conector:3c4e84476` desplegada con `infra/aplicar.sh veridy` (`conector_tag` en `infra/veridy/terraform/terraform.tfvars`); el grupo de contenedores de Veridy se recreó, el conector corre sin reinicios y Veridy responde. |

## 8. Cómo mantenerlo

- **Regenerar los diccionarios:** descargar las fuentes en carpetas aparte (lista y enlaces en `FUENTES.md`) y correr
  `python3 kerna/comun/herramientas/generar_diccionarios.py --guaguas … --forebears … --olea … --namedb … --calles … --geonames …`.
  Requiere `pyreadr` y `pandas` solo para generar.
- **Excepciones:** palabras que nunca son nombre, en `EXCEPCIONES_PALABRAS` y `EXCEPCIONES_FRASES`.
- **Tratamientos y cargos** que preceden a un nombre: `TRATAMIENTOS`.
- **Palabras tras las que un nombre-palabra en minúscula sí es persona:** `_ANTES_DE_PERSONA`.
- **Palabras que, antes de un número, no forman dirección:** `_ANTES_NUMERO_NO`.
- **Pruebas:** todo caso nuevo se agrega a `test_anonimizador.py` o a `kerna/pruebas/datos/anonimizador_casos.json`.
  Se corre con `cd kerna && python3 -m pytest pruebas/unitarias/test_anonimizador.py -q`.
- **Desplegar:**
  - Front: `kerna/front/desplegar.sh --ref HEAD`.
  - Núcleo: `infra/scripts/subir_imagen_kerna.sh nucleo --desplegar`.
  - Conector: `infra/scripts/subir_imagen_kerna.sh conector`, `conector_tag` en `infra/veridy/terraform/terraform.tfvars`
    y `infra/aplicar.sh veridy`.
