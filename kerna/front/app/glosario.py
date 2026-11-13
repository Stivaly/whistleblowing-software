"""Textos de los tooltips «?» (lenguaje simple). Las metas y precios salen de la configuración existente, no se repiten a mano."""
from __future__ import annotations

from . import formato as f
from . import informe as inf


def par_uf() -> int:
    from . import finanzas
    return round(finanzas.parametros()["uf_clp"])


NOTAS_AJUSTE = {
    "envios": "Más casos por ronda = respuestas más rápidas, más costo por hora y más riesgo de topar el límite del proveedor.",
    "reintentos": "Más reintentos rescatan más casos solos, con más gasto de IA.",
    "espera": "Esperar más da tiempo a que un proveedor se recupere; esperar menos acelera el reintento.",
    "revision": "Revisar más seguido recibe los casos antes, con más consultas a Veridy.",
    "reprocesar": "Encendido: al guardar, los casos en revisión manual vuelven a la fila una vez.",
    "evaluador": "Apagado = más rápido y barato, con menos control de las citas.",
    "candidatos": "Más artículos = revisión más cuidadosa y más costo.",
    "cadena": "Cambia qué modelo responde primero y cuál respalda.",
    "compartir": "Solo afecta a los casos nuevos.",
    "maxresp": "Más bajo = más casos marcados como lentos.",
    "alerta": "Más corto = se destacan antes los casos sin sugerencia.",
}


def _ajustes(L: str) -> dict:
    from . import ajustes
    return {it["k"]: {"t": it["l"], "q": NOTAS_AJUSTE[it["k"]], "c": "", "l": ""} for g in ajustes.GRUPOS for it in g["items"]}


def glosario() -> dict:
    meta_r = f.dec_corto(inf.META_RECALL * 100, 0)
    meta_t = f.dec_corto(inf.META_P95_MS / 1000, 0)
    pr = inf.PRECIOS_CLAUDE
    h, s = pr["Claude Haiku 5.5"], pr["Claude Sonnet 5.5"]
    precios = (f"Precios de la API de Anthropic al {inf.PRECIOS_FECHA}: Haiku 5.5, US$ {f.dec_corto(h[0], 2)} de entrada y {f.dec_corto(h[1], 2)} de salida por millón de tokens; "
               f"Sonnet 5.5, US$ {f.dec_corto(s[0], 0)} y {f.dec_corto(s[1], 0)}.")
    L = "Cómo leerlo"
    return {
        "envivo": {"t": "En vivo", "q": "Se actualiza solo cada minuto y muestra la hora del último dato recibido.",
                   "c": "Los datos de telemetría pueden tardar unos minutos en llegar: lo último que ves puede ir atrasado.", "l": L},
        "reintento_estado": {"t": "Reintento en curso", "q": "Kerna está generando de nuevo las sugerencias pendientes; el botón vuelve cuando termina.", "c": "", "l": "Ahora"},
        "estado": {"t": "Estado general", "q": "Resumen de 5 segundos: junta la salud de los modelos, los proveedores, la calidad y la rapidez. Verde = todo bien, ámbar = atención, rojo = problema.",
                   "c": "Un solo indicador en rojo hace que el estado general sea «problema»; en ámbar, «atención».", "l": L},
        "salud_modelo": {"t": "Modelos de IA", "q": "Los modelos de lenguaje que redactan la sugerencia: uno principal y uno de respaldo.", "c": "Ámbar: a veces entra el respaldo. Rojo: muchos casos pasan a revisión manual.", "l": L},
        "salud_conector": {"t": "Enlace con Veridy", "q": "El puente que lleva las denuncias de Veridy a Kerna y devuelve la sugerencia al caso.", "c": "Si hay casos esperando, se reintentan solos o pidiendo el reintento desde el panel.", "l": L},
        "salud_busqueda": {"t": "Búsqueda de leyes", "q": "Encuentra en la base de leyes los artículos más parecidos a la denuncia. Lo informa el proveedor del servicio.", "c": "Si falla, Kerna busca con su servicio propio.", "l": L},
        "salud_calidad": {"t": "Calidad", "q": "Qué tan seguido Kerna incluye el artículo correcto entre sus 5 primeras sugerencias, medido sobre un conjunto de pruebas.", "c": f"Meta: {meta_r} %.", "l": L},
        "prov_azure": {"t": "Azure OpenAI (principal)", "q": "Estado del servicio de Microsoft que ejecuta el modelo principal. Lo informa Microsoft, no nuestros errores.", "c": "Si cae, Kerna responde con Gemini, un poco más lento.", "l": "Qué hace Kerna"},
        "prov_gemini": {"t": "Google Gemini (respaldo)", "q": "Estado del servicio de Google que ejecuta el modelo de respaldo. Lo informa Google, no nuestros errores.", "c": "Si cae, Kerna sigue con Azure OpenAI; si los dos fallan, el caso pasa a revisión manual.", "l": "Qué hace Kerna"},
        "prov_voyage": {"t": "Voyage AI (búsqueda de leyes)", "q": "Estado del servicio que convierte la denuncia en una búsqueda de leyes. Lo informa Voyage AI, no nuestros errores.", "c": "Si cae, Kerna busca con su servicio propio y los casos siguen saliendo.", "l": "Qué hace Kerna"},
        "casos": {"t": "Denuncias", "q": "Cuántas denuncias de Veridy procesó Kerna en el período.", "c": "Sirve para dimensionar la carga. Un salto brusco puede ser una carga masiva o un problema.", "l": L},
        "calidad": {"t": "Acierto", "q": "Se prueba a Kerna con casos cuya respuesta correcta ya se conoce. El acierto indica con qué frecuencia el artículo correcto aparece entre sus 5 primeras sugerencias.",
                    "c": f"La meta es {meta_r} %. Se mide sobre un conjunto de pruebas, no sobre denuncias reales.", "l": L},
        "tiempo": {"t": "Tiempo de respuesta", "q": "Cuánto tarda Kerna en entregar la sugerencia. Se mira el tiempo dentro del cual terminan 9 de cada 10 casos, en su peor día del período.", "c": f"La meta es {meta_t} segundos. Más lento no rompe nada, pero la persona espera más.", "l": L},
        "costo_k": {"t": "Costo del período", "q": "Lo que cuesta atender las denuncias del período: los tokens (trozos de texto) que lee y escribe cada modelo, por su precio.", "c": precios, "l": L},
        "casos_dia": {"t": "Denuncias por día", "q": "Cada barra es un día, dividida entre las denuncias que terminaron con sugerencia y las que no.", "c": "Muchas barras rojas indican que el análisis está fallando o que faltan normas que apliquen.", "l": L},
        "modos": {"t": "Cómo se resolvieron", "q": "Reparte las denuncias entre modelo principal, modelo de respaldo, modelo local y revisión manual.", "c": "Lo ideal es que casi todo sea verde.", "l": L},
        "acierto_ley": {"t": "Acierto por ley", "q": "El mismo acierto, desglosado por cada ley. Muestra dónde Kerna se equivoca más.", "c": "La raya negra es la meta. Una ley baja suele indicar artículos mal cargados o poco claros.", "l": L},
        "valoraciones": {"t": "Valoraciones de auditores", "q": "Opinión de quienes revisan: «útil», «no útil» o «ninguno aplica» en cada sugerencia.", "c": "Es la señal de calidad más real. Sin datos hasta que haya valoraciones.", "l": L},
        "latencia": {"t": "Rapidez por día", "q": "Línea azul: la mitad de los casos del día. Línea gris: los casos más lentos (9 de cada 10 terminan antes).", "c": f"La línea punteada verde es la meta de {meta_t} s. Por encima, la respuesta es lenta.", "l": L},
        "etapas": {"t": "¿Dónde se va el tiempo?", "q": "Tiempo típico de cada etapa del análisis.", "c": "Rojo: la etapa que ocupa la mitad o más del tiempo. Ámbar: un cuarto o más.", "l": L},
        "pendientes": {"t": "Reintentos pendientes", "q": "Casos que fallaron por problemas de los modelos y se volverán a intentar solos, o ahora mismo con el botón.", "c": "Los que necesitan a una persona no se reintentan: pasan a revisión manual.", "l": L},
        "mapa": {"t": "¿Cuándo llegan las denuncias?", "q": "Muestra en qué días y horas (hora de Chile) llegan más denuncias.", "c": "Útil para planificar turnos y para elegir una hora de bajo uso al actualizar el sistema.", "l": L},
        "costo": {"t": "Costo", "q": "Tokens que leyó y escribió cada modelo realmente usado, valorizados al precio de referencia de Anthropic (gpt-5-nano ≈ Claude Haiku 5.5; gpt-5-mini ≈ Claude Sonnet 5.5).", "c": precios, "l": L},
        "leyes": {"t": "Leyes más sugeridas", "q": "Ranking de las leyes que Kerna más sugiere (cantidad de artículos sugeridos).", "c": "Ayuda a ver qué tipo de denuncias predominan.", "l": L},
        "periodo": {"t": "Período", "q": "Rango de fechas que cubrirá el informe.", "c": "Períodos más largos suavizan altibajos; más cortos muestran lo reciente.", "l": "Qué pasa si cambia"},
        "fmt_pdf": {"t": "PDF", "q": "Documento listo para leer, imprimir o adjuntar a un correo, con gráficos y conclusiones.", "c": "Ideal para comités y auditorías. No se edita fácilmente.", "l": "Cuándo usarlo"},
        "fmt_xlsx": {"t": "Excel (XLSX)", "q": "Planilla con una hoja por sección, con tablas listas para trabajar.", "c": "Ideal si quieres filtrar, hacer tus propios gráficos o cruzar datos.", "l": "Cuándo usarlo"},
        "fmt_csv": {"t": "CSV", "q": "Un único archivo de texto con todas las cifras en una tabla larga (separador «;»).", "c": "Ideal para cargarlo en otro programa o base de datos.", "l": "Cuándo usarlo"},
        "neg_estado": {"t": "Estado del negocio", "q": "Resume si Kerna como servicio va bien: clientes que lo usan, margen y riesgos.", "c": "Rojo si la utilidad es negativa; ámbar si hay algo por vigilar.", "l": L},
        "neg_clientes_k": {"t": "Clientes activos", "q": "Clientes que enviaron al menos una denuncia en los últimos días (el resto está en riesgo).", "c": "Un cliente sin uso reciente es candidato a abandonar el servicio.", "l": L},
        "neg_denuncias_k": {"t": "Denuncias procesadas", "q": "Total de denuncias analizadas entre todos los clientes en el período.", "c": "Es la base de los ingresos: más denuncias, más uso del plan y más costo de IA.", "l": L},
        "neg_ingreso": {"t": "Ingreso del período", "q": "La tarifa anual en UF de cada cliente, repartida por los días del período.", "c": "Es lo que se factura por contrato, no por denuncia.", "l": L},
        "neg_costo": {"t": "Costo de servir", "q": "Inteligencia artificial (con tope según el plan), infraestructura y soporte de cada cliente.", "c": "Sobre el tope de IA del plan, las consultas pasan al modo local sin costo.", "l": L},
        "neg_margen": {"t": "Margen operativo", "q": "Lo que queda del ingreso después de servir a los clientes, pagar la parte de Veridy y los costos fijos.", "c": "Verde sobre 60 %, ámbar entre 30 y 60 %, rojo bajo 30 %.", "l": L},
        "neg_utilidad": {"t": "Utilidad", "q": "Lo que queda al final: después de depreciación, interés del crédito e impuesto de primera categoría.", "c": "Es el resultado del período, no una proyección.", "l": L},
        "neg_adopcion_k": {"t": "Valoradas por auditores", "q": "Qué parte de las denuncias tuvo su sugerencia valorada por una persona como útil o no útil.", "c": "Si casi nadie valora, no sabemos si las sugerencias sirven. Conviene pedirlo más.", "l": L},
        "neg_sug": {"t": "Con sugerencia", "q": "De cada 100 denuncias, cuántas terminaron con una sugerencia de leyes lista.", "c": "Si baja, más casos requieren revisión manual.", "l": L},
        "neg_clientes": {"t": "Clientes", "q": "Cada fila es un cliente: cuánto usa de lo contratado, cuánto ingresa y cuesta, y cuándo fue su último uso.", "c": "Uso muy bajo o muy alto del plan, o días sin actividad, son señales para contactar al cliente.", "l": L},
        "neg_denuncias": {"t": "Denuncias por cliente", "q": "Evolución diaria del volumen de cada cliente, apilado.", "c": "Una franja que desaparece significa que ese cliente dejó de usar Kerna.", "l": L},
        "neg_adopcion": {"t": "Adopción", "q": "Embudo: de las denuncias recibidas, cuántas recibieron sugerencia, cuántas fueron valoradas y cuántas valoradas resultaron útiles.", "c": "Barras cortas en valoración indican poca participación de los auditores.", "l": L},
        "neg_resultado": {"t": "Resultado del período", "q": "Cómo se pasa del ingreso a la utilidad, con todos los costos.", "c": "Las barras muestran cada partida como parte del ingreso.", "l": L},
        "neg_supuestos": {"t": "Supuestos", "q": "Los supuestos del plan de negocio no se editan aquí.", "c": "Cambian en el archivo de parámetros financieros o con variables de entorno.", "l": L},
        "proyeccion": {"t": "Proyección a 5 años", "q": "Ingresos, costos y utilidad de cada año según el plan de negocio: clientes esperados por año y precios de cada plan.", "c": "Sirve para decidir precios o planes, no para comprometer cifras. El año 0 es 2026; el año 1 es 2027.", "l": L},
        "inf_veredicto": {"t": "Veredicto", "q": "Una frase que resume los 6 indicadores de arriba.", "c": "Rojo si alguno está bajo su meta; ámbar si alguno pide atención; verde si todos cumplen.", "l": L},
        "inf_serie": {"t": "Acierto en las últimas mediciones", "q": "Cada punto es una medición del acierto, de la más antigua a la más reciente.", "c": f"La línea punteada es la meta de {meta_r} %.", "l": L},
        "inf_anon": {"t": "Datos personales ocultados", "q": "De los casos que traen cada tipo de dato (nombre, correo, cargo), en cuántos el anonimizador lo detectó antes de enviarlo a la IA.", "c": "Barras cortas indican datos que podrían salir sin ocultar.", "l": L},
        "inf_tokens": {"t": "Tokens", "q": "Los tokens son trozos de texto: lo que el modelo lee (entrada) y escribe (salida). Con ellos se calcula el costo.", "c": precios, "l": L},
        "inf_rent": {"t": "Rentabilidad", "q": "Lo que queda de cada cliente después de servirlo, en UF, durante el período.", "c": "Verde: margen. Gris: costo de servir.", "l": L},
        "inf_incid": {"t": "Incidentes", "q": "Casos que pasaron a revisión manual y fallas de proveedores o modelos, con su motivo.", "c": "Muchas fallas del mismo proveedor suelen indicar un límite de uso o una caída.", "l": L},
        "inf_datos": {"t": "Datos", "q": "Todas las tablas del informe. Abre la que necesites.", "c": "También están completas en Excel y CSV.", "l": L},
        "aj_estado": {"t": "¿Se aplica ya?", "q": "«Activo» lo usa el conector en su próxima ronda; «Aún no» queda guardado y se aplicará cuando Kerna lo lea.", "c": "", "l": ""},
        **_ajustes(L),
        "ingresos_uf": {"t": "Ingresos (UF)", "q": "Es la proyección del plan de negocio: lo que se espera facturar cada año, en UF, con los clientes esperados por año. Así, los 638 UF del año 1 salen de 5 clientes.", "c": "El año 0 es 2026, así que el año 1 es 2027. Para pasar las UF a pesos se usa una UF supuesta de {uf} pesos: es un valor configurable que falta confirmar con el valor oficial.".replace("{uf}", f.miles(par_uf())), "l": L},
    }
