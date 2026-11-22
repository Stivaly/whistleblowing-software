"""Denuncias de la demo del panel (sección «Denuncias»), con la respuesta que corresponde a cada una.

Viven en el front, no en una base de datos. Cada caso trae el relato completo (con nombres, RUT, teléfonos y correos, para que pase por el
anonimizador del núcleo como pasaría una denuncia real) y lo que debería sugerir Kerna:

- `tipo`: `karin`, `datos` o `penal` (la ley del corpus que aplica) o `fuera` (la ley no está en el corpus de la demo: no debe haber sugerencia).
- `articulos`: (id del fragmento en el corpus, etiqueta). Una sugerencia coincide si incluye al menos uno de ellos.
- `banco`: en los casos `fuera`, id del caso del banco de evaluación (kerna/evaluacion/datos/denuncias_desarrollo_20261115_etiquetadas.json)
  que quedó sin sugerencia en las 4 corridas más recientes con la cadena desplegada (dva2, dva3, dvb2, dvb3 del 2026-11-15).
- `fuera`: solo en `tipo == "fuera"`, la ley que sí aplica y que el corpus no tiene.

Los ids son los del corpus `normativa_cl` (kerna/evaluacion/datos/corpus_texto_*.md); `pruebas/unitarias/test_front_demo_denuncias.py`
comprueba que existan en el corpus vigente.
"""
from __future__ import annotations

CT = "Código del Trabajo"
L196 = "Ley 19.628 (reformada por la 21.719)"
L203 = "Ley 20.393"
EA = "Estatuto Administrativo municipal (Ley 18.883)"

CASOS: tuple[dict, ...] = (
    {
        "id": "acoso-laboral-jefatura", "tipo": "karin", "titulo": "Acoso laboral de una jefatura",
        "texto": (
            "Trabajo hace cuatro años en la bodega central de Distribuidora Andina SpA, en Quilicura. Desde marzo, mi jefe directo, "
            "Rodrigo Valenzuela Soto (RUT 14.582.391-9), me grita frente a mis compañeros, me llama «inútil» y «viejo lento» y me quitó "
            "las funciones de inventario sin explicación. Ya no me incluye en las reuniones del equipo y me deja solo en el turno de noche. "
            "El 12 de septiembre me dijo que si no renunciaba «se iba a encargar de que me echaran». Desde entonces duermo mal y estoy "
            "en tratamiento por angustia. Se lo conté a la encargada de personas, Carolina Fuentes, y me dijo que «es su estilo» y que "
            "no hiciera problemas. Soy Marcelo Quiroga, vivo en Los Aromos 1450, Quilicura. Mi teléfono es +56 9 8123 4567 y mi correo "
            "marcelo.quiroga@correo.cl. Pido que se investigue y que me protejan mientras tanto."),
        "articulos": (("207436-karin-art-2", f"{CT}, art. 2"), ("207436-karin-art-211-a", f"{CT}, art. 211-A"),
                      ("207436-karin-art-211-b", f"{CT}, art. 211-B"), ("207436-karin-art-211-b-bis", f"{CT}, art. 211-B bis"),
                      ("207436-karin-art-211-c", f"{CT}, art. 211-C")),
    },
    {
        "id": "acoso-sexual-empresa", "tipo": "karin", "titulo": "Acoso sexual de un supervisor",
        "texto": (
            "Soy cajera de la sucursal Maipú de Supermercados El Roble Ltda. Mi supervisor, Hernán Pizarro Lagos, me escribe por WhatsApp "
            "al +56 9 7654 3210 mensajes fuera de horario: me dice que me veo «muy linda con el uniforme», me pide fotos y me invita a su "
            "departamento en Avenida Pajaritos 3380. Cuando le dije que no, me cambió el turno al de fin de semana y me dijo que «los "
            "favores se pagan». El 3 de octubre me tocó la espalda y la cintura en la bodega, aunque le pedí que parara. Tengo capturas "
            "de los mensajes y una compañera, Daniela Reyes (RUT 17.306.654-6), lo vio. Mi nombre es Paola Contreras Mena, RUT "
            "12.874.509-2, y mi correo es paola.contreras@correo.cl. Tengo miedo de ir a trabajar y quiero que me separen de él mientras "
            "se investiga."),
        "articulos": (("207436-karin-art-2", f"{CT}, art. 2"), ("207436-karin-art-211-a", f"{CT}, art. 211-A"),
                      ("207436-karin-art-211-b-bis", f"{CT}, art. 211-B bis"), ("207436-karin-art-211-c", f"{CT}, art. 211-C"),
                      ("207436-karin-art-211-e", f"{CT}, art. 211-E")),
    },
    {
        "id": "acoso-municipalidad", "tipo": "karin", "titulo": "Acoso laboral en una municipalidad",
        "texto": (
            "Soy funcionaria de planta de la Municipalidad de Lo Prado, en la Dirección de Desarrollo Comunitario. El director, Jaime "
            "Ortúzar Beltrán, me humilla en las reuniones, me dice que «las mujeres como yo no sirven para cargos de responsabilidad» y "
            "me asignó tareas de archivo para dejarme sin funciones. Revisa mis permisos médicos con burlas y amenazó con iniciarme un "
            "sumario «para que aprenda». Presenté un reclamo a la alcaldía en agosto y no he tenido respuesta; el municipio no tiene un "
            "protocolo de prevención conocido. Me llamo Silvia Araya Núñez, RUT 9.561.238-5, trabajo en calle Neptuno 4500, Lo Prado. "
            "Pueden contactarme al teléfono 22 555 0147 o al correo silvia.araya@muniloprado.cl. Solicito que se investigue en "
            "un sumario administrativo y se adopten medidas de resguardo."),
        "articulos": (("30256-karin-art-82", f"{EA}, art. 82"), ("30256-karin-art-123", f"{EA}, art. 123"),
                      ("30256-karin-art-126", f"{EA}, art. 126"), ("30256-karin-art-127", f"{EA}, art. 127"),
                      ("191865-karin-art-14", "Ley 18.575 (Bases de la Administración), art. 14")),
    },
    {
        "id": "datos-brecha-seguridad", "tipo": "datos", "titulo": "Filtración de datos de clientes",
        "texto": (
            "Soy el jefe de sistemas de Financiera Pacífico SpA. El 18 de octubre un proveedor externo dejó expuesta, sin contraseña, la "
            "base con los datos de 42.000 clientes: nombre, RUT, dirección, correo, teléfono y el estado de sus deudas. Estuvo accesible "
            "desde internet nueve días. Avisé a la gerente general, Mónica Salgado Ibarra, y decidió no informar a los clientes ni a "
            "ninguna autoridad porque «sería un escándalo». Ya aparecieron clientes reclamando llamadas de estafadores que conocen su "
            "deuda exacta. La empresa tampoco cifra esa base ni registra quién la consulta. Me llamo Tomás Burgos Rivas, RUT "
            "16.043.827-4, y escribo desde tburgos@correo.cl; mi número es +56 9 6543 2109. Pido que se investigue la falta de "
            "medidas de seguridad y de aviso."),
        "articulos": (("141599-2026-12-01-art-14-quinquies", f"{L196}, art. 14 quinquies"), ("141599-2026-12-01-art-14-sexies", f"{L196}, art. 14 sexies"),
                      ("141599-2026-12-01-art-34-ter", f"{L196}, art. 34 ter"), ("141599-2026-12-01-art-14-bis", f"{L196}, art. 14 bis")),
    },
    {
        "id": "datos-salud-whatsapp", "tipo": "datos", "titulo": "Datos de salud publicados en un grupo",
        "texto": (
            "Trabajo en el taller de Metalúrgica Cordillera S.A., en San Bernardo. Mi jefe de turno, Patricio Neira Campos, publicó en el "
            "grupo de WhatsApp de los 60 trabajadores una foto de mi licencia médica, con mi diagnóstico de depresión y el tratamiento "
            "que sigo, y escribió que «así cualquiera falta». Nunca autoricé que mis datos de salud se compartieran con nadie. Varios "
            "compañeros me hacen bromas desde entonces. Pedí por correo que borraran el mensaje y el área de personas, a cargo de Gloria "
            "Tapia, dijo que «no hay nada que borrar porque es un grupo interno». Me llamo Jorge Ibáñez Parra, RUT 13.720.915-2, vivo en "
            "Los Nogales 220, San Bernardo, y mi correo es jorge.ibanez@correo.cl. Quiero que se sancione la difusión y que se elimine "
            "la información."),
        "articulos": (("141599-2026-12-01-art-16", f"{L196}, art. 16"), ("141599-2026-12-01-art-16-bis", f"{L196}, art. 16 bis"),
                      ("141599-2026-12-01-art-14-bis", f"{L196}, art. 14 bis"), ("141599-2026-12-01-art-34-ter", f"{L196}, art. 34 ter")),
    },
    {
        "id": "penal-cohecho-permiso", "tipo": "penal", "titulo": "Soborno a un funcionario para obtener un permiso",
        "texto": (
            "Soy contador de Constructora Los Alerces S.A. En julio, el gerente de proyectos, Ricardo Maldonado Vera (RUT 10.458.736-4), "
            "me ordenó pagar en efectivo $12.000.000 a un inspector de la Dirección de Obras de la Municipalidad de Ñuñoa, Luis "
            "Carrasco, para que aprobara sin revisión la recepción final de un edificio con observaciones de seguridad. Lo registró como "
            "«asesoría externa» con una boleta de una empresa que no existe. El directorio y el gerente general, Andrés Vidal, sabían, "
            "porque firmaron la orden de pago. La empresa no tiene un modelo de prevención de delitos ni un encargado de prevención, y "
            "los trabajadores nunca recibieron capacitación sobre esto. Soy Felipe Aguirre Cid, mi teléfono es +56 9 5432 1098 y mi "
            "correo faguirre@correo.cl. Tengo copia de la orden de pago y del correo con la instrucción."),
        "articulos": (("1008668-art-1", f"{L203}, art. 1"), ("1008668-art-3", f"{L203}, art. 3"), ("1008668-art-4", f"{L203}, art. 4")),
    },
    {
        "id": "penal-lavado-activos", "tipo": "penal", "titulo": "Dinero de origen dudoso movido por la empresa",
        "texto": (
            "Trabajo en finanzas de Inversiones Costa Sur Ltda., en Viña del Mar. Mi jefe, Gonzalo Pizarro Lira, y el socio principal, "
            "Esteban Riquelme, me piden desde enero recibir transferencias de personas que no son clientes y devolverlas a cuentas de "
            "terceros en el extranjero, con facturas por «servicios» que nunca se prestaron. Han pasado más de $300.000.000 así. Cuando "
            "pregunté el origen del dinero, me dijeron que no preguntara y que firmara el informe como «operaciones normales». La empresa "
            "no tiene encargado de prevención ni canal para denunciar, y nunca se reportó nada a la Unidad de Análisis Financiero. Me "
            "llamo Camila Soto Herrera, RUT 18.239.064-K, vivo en 5 Norte 1020, Viña del Mar, y mi correo es csoto@correo.cl. Pido que "
            "se investigue la responsabilidad de la empresa."),
        "articulos": (("1008668-art-1", f"{L203}, art. 1"), ("1008668-art-3", f"{L203}, art. 3"), ("1008668-art-4", f"{L203}, art. 4")),
    },
    {
        "id": 'fuera-cambio-turno-cooperativa', "tipo": "fuera", "titulo": 'Secretaria a la que le cambiaron el horario fijo por turnos',
        "fuera": 'Código del Trabajo, art. 12 (cambio de jornada; fuera del corpus, que solo tiene los artículos de Ley Karin)',
        "banco": 'DX-0008',
        "texto": 'Resumen de sentencia. Corte de Apelaciones de Rancagua, Rol N° 1.903-2024 (laboral), sentencia de 21 de noviembre de 2024. Recurrente: Sonia Ibarra Contreras. Recurrida: Cooperativa Agrícola Valle del Cachapoal Limitada.\n\nLa recurrente, secretaria administrativa de la cooperativa, interpuso un recurso de nulidad contra la sentencia del Juzgado de Letras del Trabajo de San Fernando que rechazó su demanda de tutela y cobro de prestaciones. Sostuvo que desde el 1 de marzo de 2024 la cooperativa pasó de un horario fijo de lunes a viernes, de 8:30 a 17:30, a un sistema de turnos rotativos de cuatro semanas, con dos sábados al mes, y que esa decisión era para ella una sanción disfrazada, pues se adoptó una semana después de que presentara un reclamo por la entrega tardía de su feriado. Afirmó, además, que el cambio le impedía cuidar a su madre, que vive con ella y requiere asistencia.\n\nLa cooperativa contestó que informó el nuevo sistema por circular del 2 de febrero a toda la administración, con un mes de anticipación, que lo justificó por la ampliación de la atención a socios los días sábado desde la temporada de cosecha, y que la recurrente, al igual que otras once personas, quedó incluida sin distinción. Acompañó la circular y una nómina de los doce afectados. También indicó que, ante el planteamiento de la señora Ibarra sobre el cuidado de su madre, ofreció concentrar sus sábados en una sola semana, propuesta que la trabajadora rechazó por correo del 15 de marzo.\n\nLa sentencia de primera instancia había considerado que la modificación estaba dentro de las facultades de organización del empleador, que no se afectaba la jornada pactada en su monto total ni su naturaleza, y que no existían antecedentes de que el cambio fuera una represalia, pues el reclamo por el feriado se refería a un trámite distinto y había sido resuelto en favor de la trabajadora. La recurrente alegó que el tribunal incurrió en una errónea valoración de la prueba y que omitió aplicar las normas del Código Civil sobre interpretación de los contratos, en particular la regla de que un contrato debe ejecutarse de buena fe, y las de la ley del consumidor, que citó por analogía para sostener que debía existir una información clara y previa.\n\nLa Corte consideró que el recurso no cumplía con la exigencia de señalar con precisión la causal de nulidad invocada y que, bajo la apariencia de un vicio de derecho, pretendía una nueva valoración de la prueba, lo que es ajeno a este arbitrio. Agregó que la invocación de normas de consumo era improcedente, ya que la relación entre las partes es de naturaleza laboral y no de consumo, y que las del Código Civil sólo tendrían aplicación supletoria, sin que la recurrente hubiese explicado cuál de ellas se había infringido. Por estas razones declaró inadmisible el recurso, sin pronunciarse sobre si el cambio de turnos constituía o no una modificación que requiriera el consentimiento de la trabajadora.\n\nUn voto disidente del ministro Carlos Pinochet sostuvo que la pregunta de fondo, esto es, si la decisión de pasar de un horario fijo a uno rotativo cabe dentro de las facultades de la empresa o si altera una condición esencial del contrato, merecía ser examinada y que el rechazo por razones de forma era excesivo. La mayoría respondió que esa discusión podría plantearse en otro procedimiento. Sin costas.',
        "articulos": (),
    },
    {
        "id": 'fuera-jardin-infantil', "tipo": "fuera", "titulo": 'Apoderado que reclama contra un jardín infantil',
        "fuera": 'Normas de educación parvularia (no están en el corpus)',
        "banco": 'DX-0033',
        "texto": 'Resumen de sentencia. Corte de Apelaciones de Valdivia, Rol N° 774-2025 (protección), sentencia de 16 de junio de 2025. Recurrente: Matías Soto Cárdenas. Recurrido: Jardín Infantil Rayito de Sol, de la Fundación Educacional Alerce, y su directora, Miriam Vera Torres.\n\nAlegaciones. El recurrente, padre de una niña de tres años, sostuvo que desde marzo de 2025 el jardín modificó el horario de salida de 17:00 a 16:30 sin consultar, que la educadora encargada del nivel medio menor le habría respondido «si no le sirve, busque otro» cuando reclamó, y que un día de mayo la directora le habría hablado en tono elevado y le impidió el ingreso a la sala. Afirmó que su hija comenzó a llorar al llegar, que perdió el apetito y que estos hechos, sumados a lo anterior, afectan su integridad psíquica y la de la niña. Pidió que se dejara sin efecto el cambio de horario y que se ordenara al establecimiento un trato respetuoso hacia los apoderados.\n\nInforme del recurrido. El jardín señaló que el cambio de horario fue comunicado el 28 de febrero mediante una circular en el libro de comunicaciones y por un correo del centro de padres, y que obedeció a una exigencia de la autoridad sanitaria: según la Seremi de Salud, el funcionamiento a la hora de la once debía terminar antes por razones de dotación de personal. Agregó que la norma sanitaria aplicable fue explicada a los apoderados en una reunión a la que el recurrente no asistió. Respecto de los dichos de la educadora, sostuvo que corresponden a una conversación que se prolongó a la hora de salida y en la que el recurrente actuó de manera alterada. En cuanto a la directora, negó haberle impedido el ingreso y señaló que sólo le pidió que esperara en el patio por el término de una actividad.\n\nPrueba. Los hechos de la sala se conocieron, en lo sustancial, por la declaración de una apoderada, Carolina Ríos, quien dijo haber visto desde el patio que la directora «le habló fuerte» al recurrente, pero que no escuchó las palabras. Una auxiliar, Isabel Cuevas, afirmó que «esa mañana no pasó nada». La madre de otro niño dijo que había escuchado de la educadora que «el papá estaba muy molesto». Un certificado de una psicóloga particular, de junio, indica «síntomas de ansiedad en la menor compatibles con conflictos del entorno escolar», sin señalar cuáles. El recurrente acompañó asimismo un artículo de prensa sobre la Ley de Transparencia, que invocó para pedir al jardín que entregara el expediente de la modificación del horario, petición que no fue formulada previamente a la recurrida.\n\nContexto del conflicto. El recurrente y el jardín habían tenido otro desencuentro en 2024, cuando él retiró a su hija sin avisar y la dirección llamó a Carabineros por no ubicarlo; el recurrente califica el episodio como «un abuso» y la recurrida como «una medida de resguardo habitual». El día de la discusión de mayo, según el libro de novedades que el jardín exhibió, la educadora anotó «apoderado alterado, se le explica el procedimiento», sin hora ni firma del apoderado. El recurrente afirma que esa anotación se escribió después. Un tercer apoderado dijo que en el jardín «a veces se levanta la voz, pero con todos igual» y que su hijo está contento.\n\nLo resuelto. La Corte rechazó el recurso. Estimó, respecto del horario, que la decisión era de la competencia del establecimiento y se había comunicado de manera suficiente, y que su fundamento sanitario no había sido desvirtuado, sin perjuicio de que el recurrente pudiera reclamar ante la Seremi si estimaba que el motivo era inexacto. En cuanto al trato, consideró que los hechos se conocían por versiones contradictorias y por testigos de oídas, que no se había acreditado una conducta arbitraria o ilegal, y que un desencuentro entre un apoderado y el personal, aun incómodo, no configura por sí solo una afectación de garantías. Respecto de la petición de acceso, la declaró inadmisible por no haberse solicitado antes al jardín.\n\nHubo voto disidente parcial del ministro Raúl Jaramillo, quien habría acogido sólo en cuanto a ordenar al jardín formular por escrito, en el plazo de diez días, las razones del cambio de horario. Sin costas.',
        "articulos": (),
    },
    {
        "id": 'fuera-turno-aseo', "tipo": "fuera", "titulo": 'Auxiliar de aseo con cambio de turno y una amonestación',
        "fuera": 'Código del Trabajo, art. 12 (cambio de jornada; fuera del corpus, que solo tiene los artículos de Ley Karin)',
        "banco": 'DX-0126',
        "texto": 'Segundo Juzgado de Letras del Trabajo de Santiago, rol O-3318-2026. Demanda de doña Gladys Maturana Pinilla, auxiliar de aseo de la Clínica Dental Alameda, contra la Sociedad de Servicios Integrales Aurora SpA, su empleadora, y contra la Inmobiliaria Cordillera Ltda., dueña del edificio donde presta funciones.\n\nLa demandante contó que desde agosto de 2026 su turno fue cambiado de 7:00 a 15:00 horas a uno de 13:00 a 21:00, que el nuevo supervisor, don Ismael Quiroga Barría, le dijo frente a otras trabajadoras que «así no se limpia un pasillo» y que más tarde recibió una amonestación escrita por una mancha en un baño. Afirmó que el cambio de horario le impidió retirar a su hijo del colegio y que se sintió humillada. Pidió que se declarara que hubo vulneración de sus derechos fundamentales y una indemnización de tres millones de pesos.\n\nLa empleadora respondió que el contrato firmado en 2023 contempla turnos rotativos, que el edificio redujo el horario de atención del primer piso y que el reto del supervisor fue un episodio único, de tono seco pero sin insultos, y que la amonestación se basó en una inspección con fotografías. Sostuvo que en esos mismos días se ajustaron los turnos de otras cinco trabajadoras. La mandante alegó, además, que no es parte de la relación laboral y que, de existir algún perjuicio, la actora debía accionar solo contra quien la contrató. En subsidio, invocó las reglas del Código Civil sobre mandato y responsabilidad por hecho ajeno para sostener que no responde de los dichos de un dependiente de otra empresa.\n\nLa demandada principal agregó que la demandante firmó, el 30 de agosto, un documento donde tomaba conocimiento del nuevo horario, aunque la actora dice que lo firmó sin leerlo y bajo la presión de perder el turno. Dos compañeras de trabajo, citadas como testigos, declararon que el supervisor «es de carácter fuerte con todas» y que nunca lo vieron levantar la voz de forma ofensiva. Una tercera, ya desvinculada, contó que la actora lloró ese día, pero no escuchó lo dicho. El juez también examinó si la tutela, que debe interponerse dentro de sesenta días, había sido presentada a tiempo, pues la demandante contó el plazo desde la amonestación y la empleadora, desde el cambio de horario; el tribunal indicó que, aun contado de la forma más favorable, la acción estaba en plazo, pero que la discusión sobre cuál era el hecho que daba inicio al cómputo seguía siendo relevante para una eventual nueva demanda.\n\nLo resuelto. El tribunal rechazó la demanda. Razonó que la calificación de la conducta como vulneración de derechos fundamentales exige un menoscabo de cierta entidad que no se desprende de un solo comentario, y que el cambio de turno estaba cubierto por el ejercicio de la facultad de organizar la jornada. Respecto de la mandante, declaró que la discusión sobre su calidad de dueña de la obra o empresa era innecesaria. Dejó expresamente a salvo el derecho de la actora de presentar una denuncia ante la Inspección del Trabajo si aparecieran hechos nuevos y de reclamar, en otro juicio, por el cumplimiento del plazo de aviso del cambio de jornada. No condenó en costas.',
        "articulos": (),
    },
)

POR_ID = {c["id"]: c for c in CASOS}
