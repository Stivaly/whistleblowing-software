# Fuentes de los diccionarios del anonimizador

Generados el 2026-11-22 con `kerna/comun/herramientas/generar_diccionarios.py` (minúsculas, sin tildes). Para regenerarlos,
descargar las fuentes en carpetas aparte y correr el script con sus rutas (ver su docstring).

| Archivo | Fuente | Licencia |
|---|---|---|
| nombres.txt | Paquete R `guaguas` 0.3.0 (CRAN): nombres inscritos en el Registro Civil de Chile 1920-2021, ≥ 200 inscripciones; `nombres-propios-es.txt` y `nombres-propios-ar.txt` de github.com/olea/lemarios | guaguas: GPL-3 (datos públicos del Registro Civil); olea/lemarios: dominio público |
| apellidos.txt | https://forebears.io/chile/surnames (rangos 1-793) y `apellidos-es.txt` de olea/lemarios (INE España) | Datos públicos del sitio; dominio público |
| otros.txt | github.com/smashew/NameDatabases (`first names/all.txt`, `surnames/all.txt`: varios países y culturas) y nombres de `guaguas` con 20 a 199 inscripciones | Dominio público; GPL-3 |
| palabras.txt, verbos.txt, lemario.txt.gz | `lemario-general-del-espanol.txt` y `verbos-espanol-conjugaciones.txt` de olea/lemarios | Dominio público |
| calles.txt | OpenStreetMap: vías `highway` con `name` dentro de Chile, vía Overpass API | © colaboradores de OpenStreetMap, ODbL 1.0 |
| lugares.txt | GeoNames `cities15000` (nombres y nombres alternativos) y `countryInfo` | CC BY 4.0, geonames.org |
