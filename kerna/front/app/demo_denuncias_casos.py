"""Denuncias de la demo del panel (sección «Denuncias»), con la respuesta que corresponde a cada una.

Viven en el front, no en una base de datos. Cada caso trae el relato completo (con nombres, RUT, teléfonos y correos, para que pase por el
anonimizador del núcleo como pasaría una denuncia real) y lo que debería sugerir Kerna:

- `tipo`: `karin`, `datos` o `penal` (la ley del corpus que aplica) o `fuera` (la ley no está en el corpus de la demo: no debe haber sugerencia).
- `articulos`: (id del fragmento en el corpus, etiqueta). Una sugerencia coincide si incluye al menos uno de ellos.
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
        "id": "fuera-consumidor-garantia", "tipo": "fuera", "titulo": "Tienda que no respeta la garantía de un producto",
        "fuera": "Ley del Consumidor (19.496)",
        "texto": (
            "Compré el 2 de septiembre un notebook en la tienda Electro Hogar de Mall Plaza Oeste por $489.990. A las tres semanas dejó de "
            "encender. Llevé el equipo con la boleta y el vendedor, Cristián Muñoz, me dijo que la garantía «no cubre fallas de fábrica» "
            "y que tenía que pagar la reparación. Reclamé en el servicio al cliente y me ofrecieron un cambio por un modelo más barato, "
            "sin devolver la diferencia. Llevo seis semanas sin el computador, que uso para estudiar. Me llamo Valentina Rojas Pino, RUT "
            "17.306.654-6, vivo en Pasaje Los Lirios 88, Cerrillos, y mi teléfono es +56 9 4321 0987. Quiero que me cambien el producto "
            "o me devuelvan el dinero, como corresponde por la garantía legal."),
        "articulos": (),
    },
    {
        "id": "fuera-transito-conductor", "tipo": "fuera", "titulo": "Conductor ebrio que chocó autos estacionados",
        "fuera": "Ley de Tránsito (18.290)",
        "texto": (
            "El sábado 14 a las 02:30 de la madrugada, un vecino de mi calle, Sergio Bravo Tapia (patente KRBT-45), llegó manejando en "
            "evidente estado de ebriedad por Avenida Departamental, en La Florida, e impactó tres autos estacionados frente al número "
            "2150. Se bajó trastabillando, no quiso esperar a Carabineros y se fue a su casa. Los daños son importantes y hay una "
            "camioneta con el parabrisas destrozado. Tenemos el video de la cámara del edificio, donde se ve cómo viene zigzagueando y la "
            "hora exacta. No es la primera vez que maneja así. Mi nombre es Marta Cáceres Vega, mi teléfono es +56 9 3210 9876 y mi "
            "correo es mcaceres@correo.cl. Pido que se sancione por conducir en estado de ebriedad y que respondan por los daños."),
        "articulos": (),
    },
    {
        "id": "fuera-tributaria-boletas", "tipo": "fuera", "titulo": "Venta de comida sin boletas ni iniciar actividades",
        "fuera": "Código Tributario y Ley del IVA (DL 825)",
        "texto": (
            "Un contribuyente de mi barrio, Óscar Tello Mardones (RUT 12.874.509-2), vende almuerzos por encargo todos los días desde "
            "su casa en Pasaje Los Olivos 340, Peñalolén, y los despacha por Instagram. Atiende más de 80 pedidos diarios, pero nunca "
            "entrega boleta, no ha iniciado actividades ante el Servicio de Impuestos Internos y recibe todo por transferencias a una "
            "cuenta de su madre. Presume en redes de que «no paga ni un peso de IVA ni de renta» y de que tiene tres vehículos nuevos. "
            "Competir así es injusto para quienes pagamos nuestros impuestos. Soy Elena Vargas Díaz, mi teléfono es +56 9 2109 8765 y "
            "mi correo es evargas@correo.cl. Pido que se fiscalice la declaración de sus ventas."),
        "articulos": (),
    },
)

POR_ID = {c["id"]: c for c in CASOS}
