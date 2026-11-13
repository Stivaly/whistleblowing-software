# Triage de casos del dataset de evaluación (2026-11-12)

Dataset `datos/denuncias_publicas.json` (fuera de git). Detalle por caso en `datos/triage_casos.json` (fuera de git; `articulos_corpus` = etiqueta original mapeada, `articulos_corregidos`, `articulos_propuestos`, `confianza`, `cambios_etiqueta`, banderas). Este resumen no contiene textos.

Criterio: `si` = algún artículo etiquetado, mapeado al corpus vigente con la lógica de `recall_retriever.py` (concordancia 19.628), es central para los hechos. `control` = caso `ninguna` (más dos casos etiquetados 21.643 que el propio dataset define para medir falsos positivos). `no` = lo central está fuera del corpus (Código Penal, Ley 19.913, Carabineros/FF.AA., Ley 20.285, Ley 19.496, Constitución) o no hay artículo etiquetado en el corpus. Partición: jurídicos = desarrollo, reddit = prueba. Los artículos propuestos son una sugerencia; solo los de confianza alta pasaron a `articulos_corregidos`.

## Correcciones de etiqueta (decisión del orquestador, 2026-11-12)

La etiqueta original no se sobrescribe; `recall_retriever.py --triage ... --etiqueta corregida` usa `articulos_corregidos`.

- CT 154 bis (reserva de información del trabajador) -> 154 ter: en el corpus 154 bis es el protocolo de acoso para empresas sin reglamento. Casos: DEN-0065, DEN-0066, DEN-0067, DEN-0074.
- CT 211-B (medidas de resguardo) -> 211-B bis: 211-B trata los principios de la investigación. Casos: DEN-0010, DEN-0012, DEN-0016, DEN-0022, DEN-0029 (en DEN-0010 y DEN-0022 la etiqueta corregida quedó sustituida por los puntos siguientes).
- Propuestos aceptados por confianza alta (se suman a `articulos_corregidos`): DEN-0003, DEN-0005, DEN-0016, DEN-0017, DEN-0024, DEN-0029, DEN-0032, DEN-0036, DEN-0040, DEN-0057, DEN-0060, DEN-0068, DEN-0069, DEN-0070, DEN-0073, DEN-0081, DEN-0082, DEN-0086, DEN-0091.
- Pasan de `no` a `si` con artículo claro: DEN-0051, DEN-0062, DEN-0064, DEN-0090. Siguen `no`: DEN-0033, DEN-0072, DEN-0075, DEN-0078 (artículo no claro o la persona jurídica/titular no es el centro).

## Estatutos públicos agregados al corpus (commit 62b8c6cda: Leyes 18.575, 18.834, 18.883, 18.695)

El corpus solo trae los artículos que modificó la Ley Karin; faltan los que definen la prohibición de acoso (Ley 18.834 art. 84 letras l y m; Ley 18.883 art. 82 letras l y m) y la prescripción (18.834 art. 159). Los arts. 82, 84, 154, 155, 158 y 159 se cargaron el 2026-11-12 (`articulos_incluir`). Pasan de `no` a `si`, con CT 2 ya no esperado (el CT no rige a funcionarios): DEN-0008 (18.883 123, 18.883 127), DEN-0009 (18.834 125, 18.834 121), DEN-0018 (18.883 123, 18.883 127), DEN-0021 (18.575 14), DEN-0022 (18.883 133, 18.883 135), DEN-0026 (18.883 123, 18.883 127). Carabineros y Ejército siguen `no` (DEN-0010, 0011, 0019, 0027): su norma no está en el corpus.

## Conteos

| Partición | si | no | control | total |
|---|---|---|---|---|
| desarrollo | 42 | 27 | 8 | 77 |
| prueba | 13 | 7 | 16 | 36 |

| Ley principal (dataset) | si | no | control |
|---|---|---|---|
| Ley 21.643 / CT / estatutos | 22 | 5 | 2 |
| Ley 20.393 | 9 | 15 | 0 |
| Ley 19.628 reformada (21.719) | 24 | 14 | 0 |
| ninguna | 0 | 0 | 22 |

En alcance: 55; con un solo artículo en la etiqueta corregida: 17.

## Decisión por caso

| id | fuente | partición | decisión (confianza) | etiqueta original (corpus) | etiqueta corregida | propuestos | motivo |
|---|---|---|---|---|---|---|---|
| DEN-0001 | reddit | prueba | si (media) | CT 2, CT 211-a, CT 211-b, CT 211-c | CT 2, CT 211-a, CT 211-b, CT 211-c | - | Acoso laboral de la jefatura durante licencia; CT 2 y 211 aplicables (mezcla con incumplimientos laborales). |
| DEN-0002 | reddit | prueba | control (media) | CT 2, CT 211-a | CT 2, CT 211-a | - | Etiqueta 21.643 pero el dataset la define para medir sobreclasificación: no hay conducta dirigida a la persona; se trata como control. |
| DEN-0003 | reddit | prueba | si (alta) | CT 2, CT 211-a, CT 211-b, CT 211-c | CT 2, CT 211-a, CT 211-b, CT 211-b-bis, CT 211-c, CT 211-e | CT 211-b-bis, CT 211-e | Acoso sexual de un jefe; la empresa no remitió a la DT ni sancionó. |
| DEN-0004 | reddit | prueba | si (alta) | CT 2, CT 211-a, CT 211-b, CT 211-c | CT 2, CT 211-a, CT 211-b, CT 211-c | - | Acoso laboral y episodio sexual de la jefa de tienda; CT 2 y 211. |
| DEN-0005 | reddit | prueba | si (alta) | CT 2, CT 211-a | CT 2, CT 211-a, CT 211-c | CT 211-c | Violencia de clientes contra cajera: CT 2 letra c y protocolo 211-A. |
| DEN-0006 | reddit | prueba | si (baja) | CT 2 | CT 2 | - | Caso límite entre mala gestión y acoso laboral (menoscabo por presión constante). |
| DEN-0007 | reddit | prueba | control (media) | CT 2 | CT 2 | - | Etiqueta 21.643 pero es conflicto entre pares sin hostigamiento (el dataset lo marca para falsos positivos); se trata como control. |
| DEN-0008 | fallo_judicial | desarrollo | si (media) | CT 2 | 18.883 123, 18.883 127 | - | Acoso en CESFAM municipal: destitución por la prohibición de acoso (Ley 18.883 art. 123) y sumario (127), ahora en el corpus. |
| DEN-0009 | fallo_judicial | desarrollo | si (media) | CT 2 | 18.834 125, 18.834 121 | - | Acoso en servicio público: sanción y proporcionalidad (Ley 18.834 arts. 121 y 125, ahora en el corpus; la prescripción, art. 159, no está). |
| DEN-0010 | fallo_judicial | desarrollo | no (media) | CT 2, CT 211-b | CT 2, CT 211-b-bis | CT 211-b-bis | Acoso entre pares en Carabineros (régimen estatutario propio); los candidatos son del CT. |
| DEN-0011 | fallo_judicial | desarrollo | no (alta) | CT 211-c | CT 211-c | - | Carabineros se rige por su regulación especial; el CT no aplica (el dataset lo usa para medir aplicación errónea). |
| DEN-0012 | fallo_judicial | desarrollo | si (baja) | CT 211-b | CT 211-b-bis | CT 211-b-bis | Separación preventiva tras denuncia de un trabajador del Cuerpo de Bomberos; el denunciado es voluntario (no trabajador). |
| DEN-0013 | fallo_judicial | desarrollo | si (alta) | CT 211-c, CT 211-d | CT 211-c, CT 211-d | - | Informe de investigación de la DT y su impugnación: CT 211-C y 211-D. |
| DEN-0014 | fallo_judicial | desarrollo | si (baja) | CT 154, CT 211-a, CT 211-b, CT 211-c | CT 154, CT 211-a, CT 211-b, CT 211-c | - | Investigación interna de acoso tramitada bajo el reglamento interno; el foco es el derecho de defensa del investigado. |
| DEN-0015 | fallo_judicial | desarrollo | si (media) | CT 2, CT 211-b | CT 2, CT 211-b | CT 211-e | Despido comunicado a terceros 'por Ley Karin' y confidencialidad de la investigación. |
| DEN-0016 | fallo_judicial | desarrollo | si (alta) | CT 211-b, CT 211-c | CT 211-b-bis, CT 211-c, CT 211-d | CT 211-b-bis, CT 211-d | Demora de la DT en investigar: plazo de 30 días de CT 211-C aplicado por la Corte. |
| DEN-0017 | fallo_judicial | desarrollo | si (alta) | CT 2, CT 211-a | CT 2, CT 211-a, CT 211-b-bis | CT 211-b-bis | Violencia de un tercero (exjefe) en el lugar de trabajo y represalia a testigo. |
| DEN-0018 | fallo_judicial | desarrollo | si (media) | CT 2 | 18.883 123, 18.883 127 | - | Destitución por acoso tras sumario municipal (Ley 18.883 arts. 123 y 127, ahora en el corpus). |
| DEN-0019 | fallo_judicial | desarrollo | no (alta) | CT 2 | CT 2 | - | Acoso sexual en escuela de Carabineros (régimen estatutario); CT solo 'por analogía'. |
| DEN-0020 | fallo_judicial | desarrollo | si (media) | CT 2 | CT 2 | - | Tutela por acoso laboral y discriminación; CT 2 define el acoso (CT 485 y ss. no están en el corpus). |
| DEN-0021 | fallo_judicial | desarrollo | si (baja) | CT 2 | 18.575 14 | - | Acoso en un ministerio: protocolo de prevención de la Administración (Ley 18.575 art. 14, ahora en el corpus); el conflicto se discute en otra vía. |
| DEN-0022 | fallo_judicial | desarrollo | si (baja) | CT 211-b | 18.883 133, 18.883 135 | CT 211-b-bis | Traslado preventivo tras denuncia de acoso en salud municipal: medidas de resguardo y sobreseimiento (Ley 18.883 arts. 133 y 135, ahora en el corpus). |
| DEN-0023 | fallo_judicial | desarrollo | si (baja) | CT 2 | CT 2 | - | Hostigamiento por correos a trabajadoras de una corporación municipal; autoría no acreditada. |
| DEN-0024 | fallo_judicial | desarrollo | si (alta) | CT 2 | CT 2, CT 211-b-bis, CT 211-c | CT 211-b-bis, CT 211-c | Denuncia de acoso no investigada por exigir reiteración; CT 2 vigente exige un solo acto. |
| DEN-0025 | fallo_judicial | desarrollo | si (baja) | 19.628 2, CT 211-b | 19.628 2, CT 211-b | - | Reserva de identidades y testimonios de un sumario de acoso frente a transparencia (central: Ley 20.285; contrapeso: datos personales). |
| DEN-0026 | fallo_judicial | desarrollo | si (media) | CT 2 | 18.883 123, 18.883 127 | - | Acoso sexual de funcionario municipal y destitución (Ley 18.883 arts. 123 y 127, ahora en el corpus). |
| DEN-0027 | fallo_judicial | desarrollo | no (media) | CT 2 | CT 2 | - | Maltrato en el Ejército (régimen propio); lo central es la competencia laboral y daño moral. |
| DEN-0028 | fallo_judicial | desarrollo | no (alta) | - | - | - | Despido vulneratorio (tutela CT 485-489) sin hechos de acoso; ningún artículo mapeable del corpus. |
| DEN-0029 | dt | desarrollo | si (alta) | CT 211-a, CT 211-b | CT 211-a, CT 211-b-bis, CT 211-c | CT 211-b-bis, CT 211-c | Empleador se entera de posible acoso y la víctima pide no denunciar: 211-A, 211-B bis y 211-C. |
| DEN-0030 | reddit | prueba | no (media) | - | - | - | Contratación irregular y cotizaciones: infracción laboral/migratoria; sin artículo mapeable. |
| DEN-0031 | reddit | prueba | no (media) | - | - | - | Posible fraude a aseguradora por un taller; sin artículo mapeable ni persona jurídica clara. |
| DEN-0032 | noticia | desarrollo | si (alta) | 20.393 1 | 20.393 1, 20.393 3, 20.393 4 | 20.393 3, 20.393 4 | Facturas falsas para financiar un grupo empresarial con denuncia de un gerente: delitos económicos base (art. 1) de una persona jurídica. |
| DEN-0033 | noticia | desarrollo | no (baja) | - | - | 20.393 1 | Pyme usada para facturas falsas: sin artículo mapeable; podría re-etiquetarse con art. 1. |
| DEN-0034 | noticia | desarrollo | si (media) | 20.393 1 | 20.393 1 | 20.393 3 | Cohecho a funcionarios del SII y Tesorería por empresas: art. 1 (delitos económicos). |
| DEN-0035 | noticia | desarrollo | si (alta) | 20.393 1, 20.393 3, 20.393 4 | 20.393 1, 20.393 3, 20.393 4 | - | Cohecho de empresa minera a parlamentarios y modelo de prevención meramente formal. |
| DEN-0036 | noticia | desarrollo | si (alta) | 20.393 1 | 20.393 1, 20.393 3, 20.393 4 | 20.393 3, 20.393 4 | Soborno de pesquera a parlamentarios: persona jurídica y modelo de prevención. |
| DEN-0037 | noticia | desarrollo | si (media) | 20.393 1 | 20.393 1 | 20.393 3 | Sobornos de constructora para licitaciones públicas. |
| DEN-0038 | noticia | desarrollo | no (media) | - | - | - | Fraude al Fisco por parlamentario; la imprenta es instrumento y no hay artículo mapeable. |
| DEN-0039 | noticia | desarrollo | no (media) | - | - | - | Contrabando, lavado (Ley 19.913) y filtración policial; sin artículo mapeable. |
| DEN-0040 | noticia | desarrollo | si (alta) | 20.393 4 | 20.393 3, 20.393 4 | 20.393 3 | Denuncia por el canal del modelo de prevención y represalia: art. 4 (canal de denuncias). |
| DEN-0041 | noticia | desarrollo | si (baja) | 20.393 1 | 20.393 1 | 20.393 3 | Sobornos a concejales para favorecer a una empresa en una licitación; persona jurídica beneficiada. |
| DEN-0042 | noticia | desarrollo | no (media) | 20.393 1 | 20.393 1 | - | Cohecho de un juez (CP 248 bis); la persona jurídica pagadora no está identificada. |
| DEN-0043 | noticia | desarrollo | si (baja) | 20.393 1 | 20.393 1 | 20.393 3 | Constructora con sobornos en Argentina y presuntas coimas en Chile; relevancia chilena indirecta. |
| DEN-0044 | fallo_judicial | desarrollo | no (media) | 20.393 1 | 20.393 1 | - | Condenas a personas naturales (exalcalde, empresario) por CP 248-250, fraude al Fisco y lavado; sin persona jurídica imputada. |
| DEN-0045 | fallo_judicial | desarrollo | no (alta) | - | - | - | Cuasidelito (culposo) con supervisión judicial a la empresa; sin artículo mapeable. |
| DEN-0046 | fallo_judicial | desarrollo | no (alta) | - | - | - | Sanción administrativa de la UAF (Ley 19.913); fuera del corpus. |
| DEN-0047 | fallo_judicial | desarrollo | no (alta) | - | - | - | Multa a banco por no reportar operaciones sospechosas (Ley 19.913). |
| DEN-0048 | fallo_judicial | desarrollo | no (alta) | - | - | - | Malversación y lavado de persona natural; fuera del corpus. |
| DEN-0049 | fallo_judicial | desarrollo | no (alta) | - | - | - | Contencioso ambiental administrativo (Ley 19.300). |
| DEN-0050 | fallo_judicial | desarrollo | no (alta) | - | - | - | Cierre de cuentas por prevención de lavado (Ley 19.913); la empresa es la afectada. |
| DEN-0051 | fallo_judicial | desarrollo | si (media) | - | 20.393 1, 20.393 3 | 20.393 1, 20.393 3, 20.393 4 | Administración desleal en corredora (CP 470 N°11): art. 1 aplicaría, pero el dataset no lo etiqueta; re-etiquetable. [Pasa a si con artículo corregido.] |
| DEN-0052 | fallo_judicial | desarrollo | no (alta) | - | - | - | Nulidad civil de facturas cedidas a factoring; sin artículo mapeable. |
| DEN-0053 | fallo_judicial | desarrollo | no (alta) | - | - | - | Indemnización civil entre empresa y exempleados; el ilícito penal no se detalla. |
| DEN-0054 | reddit | prueba | no (media) | 19.628 17, 19.628 18, 19.628 19 | 19.628 17, 19.628 18, 19.628 19 | - | Cobranza telefónica diaria por deuda antigua: central Ley 19.496 art. 37; no hay reporte de deuda descrito. |
| DEN-0055 | reddit | prueba | si (media) | 19.628 17, 19.628 18 | 19.628 17, 19.628 18 | - | Amenaza de reporte a DICOM por cobro erróneo: art. 17-18 (datos de obligaciones económicas). |
| DEN-0056 | reddit | prueba | no (alta) | - | - | - | Consulta preventiva sin tratamiento indebido; sin artículo mapeable. |
| DEN-0057 | reddit | prueba | si (alta) | 19.628 4, 19.628 5, 19.628 6, 19.628 7 | 19.628 11, 19.628 4, 19.628 5, 19.628 6, 19.628 7 | 19.628 11 | Solicitud de grabaciones donde aparece el titular: derecho de acceso (art. 5) y su procedimiento. |
| DEN-0058 | reddit | prueba | no (media) | - | - | - | Estafa y toma de cuenta bancaria (Ley 20.009, 21.459); lo de datos de terceros es tangencial. |
| DEN-0059 | reddit | prueba | no (alta) | - | - | - | Opinión sobre publicación de mensajes de un diputado por un medio; sin artículo mapeable. |
| DEN-0060 | reddit | prueba | si (alta) | 19.628 4, 19.628 5, 19.628 6, 19.628 7 | 19.628 4, 19.628 5, 19.628 6, 19.628 7, 19.628 8 | 19.628 8 | Llamadas de cobranza a un número ajeno y empresa que ignora la petición de borrar el dato: supresión y rectificación. |
| DEN-0061 | reddit | prueba | si (media) | 19.628 12, 19.628 13, 19.628 3 | 19.628 12, 19.628 13, 19.628 3 | - | Uso de rutificador/patentes para identificar a un tercero: licitud y finalidad del tratamiento. |
| DEN-0062 | reddit | prueba | si (media) | - | 19.628 3 | 19.628 12, 19.628 3 | Videovigilancia de condominio: aplica 19.628 pero el dataset no cita artículos; re-etiquetable. [Pasa a si con artículo corregido.] |
| DEN-0063 | reddit | prueba | no (alta) | - | - | - | Acceso a grabaciones de cámaras públicas (Ley 20.285); hecho principal ajeno. |
| DEN-0064 | reddit | prueba | si (media) | - | 19.628 8 | 19.628 8 | Llamadas comerciales (Ley 19.496 No Molestar); derecho de oposición no etiquetado; re-etiquetable. [Pasa a si con artículo corregido.] |
| DEN-0065 | reddit | prueba | si (baja) | CT 154-bis | CT 154-ter | CT 154-ter | Filtración de grupo de WhatsApp de profesores; reserva de datos del trabajador. |
| DEN-0066 | reddit | prueba | si (media) | CT 154-bis | CT 154-ter | CT 154-ter | Monitoreo del correo de empresa por el empleador; reserva de datos del trabajador. |
| DEN-0067 | noticia | desarrollo | no (alta) | CT 154-bis | CT 154-ter | CT 154-ter | Espionaje a trabajadores por una minera en Brasil; fuera de la jurisdicción chilena. |
| DEN-0068 | noticia | desarrollo | si (alta) | 19.628 14-quinquies, 19.628 16, 19.628 2, 19.628 3 | 19.628 14-quinquies, 19.628 14-sexies, 19.628 16, 19.628 2, 19.628 3 | 19.628 14-sexies | Filtración masiva de datos sensibles de un organismo público: seguridad y sensibles. |
| DEN-0069 | noticia | desarrollo | si (alta) | 19.628 12, 19.628 13, 19.628 2 | 19.628 12, 19.628 13, 19.628 16, 19.628 16-quater, 19.628 16-ter, 19.628 2 | 19.628 16, 19.628 16-quater, 19.628 16-ter | Escaneo de iris de una menor sin consentimiento: licitud, biométricos y datos de NNA. |
| DEN-0070 | fallo_judicial | desarrollo | si (alta) | 19.628 4, 19.628 5, 19.628 6, 19.628 7 | 19.628 11, 19.628 4, 19.628 5, 19.628 6, 19.628 7 | 19.628 11 | Derecho de acceso a datos de deuda con cobro por ver el detalle. |
| DEN-0071 | fallo_judicial | desarrollo | no (alta) | - | - | - | Regulación de llamadas de cobranza entre gremio y Subtel; sin titular de datos. |
| DEN-0072 | fallo_judicial | desarrollo | no (media) | - | - | 19.628 8 | Cobranza abusiva (Ley 19.496 art. 37); sin artículo mapeable; oposición podría etiquetarse. |
| DEN-0073 | fallo_judicial | desarrollo | si (alta) | 19.628 17, 19.628 18, 19.628 19 | 19.628 17, 19.628 18, 19.628 19, 19.628 8-ter | 19.628 8-ter | Reporte a registros de deuda disputada tras fraude: art. 17-19. |
| DEN-0074 | fallo_judicial | desarrollo | si (media) | CT 154-bis | CT 154-ter | 19.628 3, CT 154-ter | Videovigilancia con audio de conductores: reserva y proporcionalidad. |
| DEN-0075 | fallo_judicial | desarrollo | no (media) | - | - | 19.628 12, 19.628 3 | Cámara de vecino: aplica 19.628 pero sin artículo etiquetado; re-etiquetable. |
| DEN-0076 | fallo_judicial | desarrollo | no (media) | - | - | - | Grabación clandestina por un canal; lo central es Constitución 19 N°4; sin artículo mapeable. |
| DEN-0077 | fallo_judicial | desarrollo | no (alta) | - | - | - | Transparencia de documentos registrales (Ley 20.285); dato personal tangencial. |
| DEN-0078 | fallo_judicial | desarrollo | no (media) | - | - | 19.628 12, 19.628 13, 19.628 3 | Extracción masiva de sentencias; sin artículo etiquetado; re-etiquetable. |
| DEN-0079 | fallo_judicial | desarrollo | no (alta) | - | - | - | Publicación de una foto en Facebook derivada a la vía penal (injurias); sin artículo mapeable. |
| DEN-0080 | fallo_judicial | desarrollo | no (alta) | - | - | - | Identidad de un denunciante anónimo ante la CMF (Ley 20.285 y DL 3538). |
| DEN-0081 | fallo_judicial | desarrollo | si (alta) | 19.628 18 | 19.628 18, 19.628 7 | 19.628 7 | Deuda publicada pese a abandono del cobro: plazo del art. 18. |
| DEN-0082 | fallo_judicial | desarrollo | si (alta) | 19.628 17, 19.628 18 | 19.628 17, 19.628 18, 19.628 7 | 19.628 7 | Facturas morosas informadas años después: art. 17-18. |
| DEN-0083 | fallo_judicial | desarrollo | si (media) | 19.628 2 | 19.628 2 | 19.628 16 | Neurodatos recogidos por un dispositivo: dato sensible. |
| DEN-0084 | fallo_judicial | desarrollo | si (baja) | 19.628 2 | 19.628 2 | - | Si el RUC es dato personal (art. 2) frente a transparencia (central: Ley 20.285). |
| DEN-0085 | fallo_judicial | desarrollo | si (alta) | 19.628 4, 19.628 5, 19.628 6, 19.628 7 | 19.628 4, 19.628 5, 19.628 6, 19.628 7 | - | Desindexación de noticias sobre condena anulada: derecho de supresión. |
| DEN-0086 | fallo_judicial | desarrollo | si (alta) | 19.628 16, 19.628 2 | 19.628 16, 19.628 16-bis, 19.628 2, 19.628 22 | 19.628 16-bis, 19.628 22 | Entrega de datos de salud a Contraloría: datos sensibles y cesión entre órganos públicos. |
| DEN-0087 | fallo_judicial | desarrollo | si (baja) | 19.628 14-bis, 19.628 14-quinquies | 19.628 14-bis, 19.628 14-quinquies | - | Acceso y divulgación indebida de datos de un cliente (secreto y seguridad); el despido es CT 160, fuera del corpus. |
| DEN-0088 | cplt | desarrollo | si (baja) | 19.628 2 | 19.628 2 | - | Video de cámaras municipales: imagen como dato personal frente a Ley 20.285. |
| DEN-0089 | cplt | desarrollo | si (media) | 19.628 12, 19.628 13, 19.628 2, 19.628 3 | 19.628 12, 19.628 13, 19.628 2, 19.628 3 | - | Amparo rechazado por tratamiento de datos personales y sensibles en grabaciones de vigilancia. |
| DEN-0090 | dt | desarrollo | si (media) | - | 19.628 16-sexies, 19.628 16-ter | 19.628 16-sexies, 19.628 16-ter, 19.628 3 | GPS y reconocimiento facial para fiscalizar licencias: sin artículo mapeable; biométricos y geolocalización son 16 ter y 16 sexies; re-etiquetable. [Pasa a si con artículo corregido.] |
| DEN-0091 | dt | desarrollo | si (alta) | 19.628 16 | 19.628 16, 19.628 16-bis, 19.628 16-quater, 19.628 22 | 19.628 16-bis, 19.628 16-quater, 19.628 22 | Acceso a fichas clínicas de niños por una oficina municipal: datos sensibles. |
| DEN-0092 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0093 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0094 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0095 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0096 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0097 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0098 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0099 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0100 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0101 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0102 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0103 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0104 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0105 | reddit | prueba | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0106 | fallo_judicial | desarrollo | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0107 | fallo_judicial | desarrollo | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0108 | fallo_judicial | desarrollo | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0109 | fallo_judicial | desarrollo | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0110 | fallo_judicial | desarrollo | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0111 | fallo_judicial | desarrollo | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0112 | fallo_judicial | desarrollo | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |
| DEN-0113 | fallo_judicial | desarrollo | control (alta) | - | - | - | Caso 'ninguna': sin artículo aplicable; sirve para medir falsos positivos. |


Actualización 2026-11-12 (artículos de definición cargados): en `articulos_corregidos` se suma 18.834 arts. 84 y 159 a DEN-0009 (el texto los cita expresamente; confianza media -> alta) y 18.883 art. 82 a DEN-0026 (cita el art. 82 letra l; confianza media -> alta), DEN-0008 y DEN-0018 (acoso laboral con destitución; el texto no cita el 82; confianza sigue media). DEN-0021 (protocolo en un ministerio; 18.575 art. 14) y DEN-0022 (traslado preventivo; 18.883 arts. 133 y 135) no cambian: no discuten la definición. 18.575 arts. 52 y 64 no se cargaron (probidad e inhabilidades, sin definición de acoso). Recall@5 retriever solo: desarrollo 0,548 antes y después; prueba 0,467 sin cambios (ver registro-pruebas.md).
