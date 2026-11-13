"""Textos de los tooltips «?» (lenguaje simple). Las metas y precios salen de la configuración existente, no se repiten a mano."""
from __future__ import annotations

from . import formato as f
from . import informe as inf


def par_uf() -> int:
    from . import finanzas
    return round(finanzas.parametros()["uf_clp"])


NOTAS_AJUSTE = {
    "envios": "Más casos juntos: más rápido, pero más cerca del límite del proveedor.",
    "reintentos": "Más reintentos rescatan más casos solos, con más gasto de IA.",
    "espera": "Esperar más da tiempo a que el proveedor se recupere.",
    "revision": "Más seguido: los casos llegan antes, con más consultas a Veridy.",
    "reprocesar": "Al guardar, los casos en revisión manual vuelven a la fila una vez.",
    "evaluador": "Apagado: más rápido y barato, con menos control de las citas.",
    "candidatos": "Más artículos: revisión más cuidadosa y más costo.",
    "cadena": "Cambia qué modelo responde primero y cuál respalda.",
    "compartir": "Solo afecta a los casos nuevos.",
    "maxresp": "Más bajo: más casos marcados como lentos.",
    "alerta": "Más corto: se destacan antes los casos sin sugerencia.",
}


def _ajustes(L: str) -> dict:
    from . import ajustes
    return {it["k"]: {"t": it["l"], "q": NOTAS_AJUSTE[it["k"]], "c": "", "l": ""} for g in ajustes.GRUPOS for it in g["items"]}


def glosario() -> dict:
    meta_r = f.dec_corto(inf.META_RECALL * 100, 0)
    meta_t = f.dec_corto(inf.META_P95_MS / 1000, 0)
    L = ""
    G = {
        "envivo": ("En vivo", "Se actualiza cada minuto; los datos pueden tardar unos minutos."),
        "reintento_estado": ("Reintento en curso", "Kerna está generando de nuevo las sugerencias pendientes."),
        "estado": ("Estado general", "Verde: todo bien. Ámbar: atención. Rojo: hay un problema."),
        "salud_modelo": ("Modelos de IA", "Los modelos que redactan la sugerencia: principal y respaldo."),
        "salud_conector": ("Enlace con Veridy", "El puente que lleva las denuncias a Kerna y devuelve la sugerencia."),
        "salud_busqueda": ("Búsqueda de leyes", "Encuentra los artículos de ley más parecidos a la denuncia."),
        "salud_calidad": ("Calidad", f"Veces que el artículo correcto sale entre los 5 primeros (meta {meta_r} %)."),
        "prov_azure": ("Azure OpenAI (principal)", "Estado del servicio de Microsoft que ejecuta el modelo principal."),
        "prov_gemini": ("Google Gemini (respaldo)", "Estado del servicio de Google que ejecuta el modelo de respaldo."),
        "prov_voyage": ("Voyage AI (búsqueda de leyes)", "Estado del servicio que busca las leyes parecidas a la denuncia."),
        "casos": ("Denuncias recibidas", "Denuncias de Veridy que Kerna procesó en el período."),
        "calidad": ("Sugerencias acertadas", f"Veces que el artículo correcto sale entre los 5 primeros (meta {meta_r} %)."),
        "tiempo": ("Tiempo de respuesta", f"Tiempo en que terminan 9 de cada 10 casos (meta {meta_t} s)."),
        "costo_k": ("Costo del período", "Lo que costó la IA al leer y escribir texto en el período."),
        "casos_dia": ("Denuncias por día", "Cada barra es un día: con sugerencia y sin sugerencia."),
        "modos": ("Cómo se resolvieron", "Reparto entre modelo principal, respaldo y revisión manual."),
        "acierto_ley": ("Acierto por ley", "El acierto de cada ley; la marca es la meta."),
        "valoraciones": ("Sugerencias útiles según auditores", "Cuántas sugerencias valoradas los auditores marcaron como útiles."),
        "latencia": ("Rapidez por día", f"Línea azul: la mitad de los casos. Gris: 9 de cada 10 (meta {meta_t} s)."),
        "etapas": ("Tiempo por etapa", "Cuánto tarda cada paso del análisis; en rojo, el que más demora."),
        "pendientes": ("Casos en espera", "Casos que fallaron y se reintentan solos o con el botón."),
        "mapa": ("Cuándo llegan las denuncias", "Días y horas (hora de Chile) con más denuncias."),
        "costo": ("Costo por modelo", "Texto leído y escrito por cada modelo, a precio de referencia."),
        "leyes": ("Leyes más sugeridas", "Las leyes con más artículos sugeridos por Kerna."),
        "periodo": ("Período", "Rango de fechas que cubre el informe."),
        "fmt_pdf": ("PDF", "Para leer, imprimir o enviar por correo."),
        "fmt_xlsx": ("Excel (XLSX)", "Una hoja por sección, para filtrar y hacer tus gráficos."),
        "fmt_csv": ("CSV", "Un archivo de texto con todas las cifras, separado por «;»."),
        "neg_estado": ("Estado del negocio", "Rojo si la utilidad es negativa; ámbar si algo se vigila."),
        "neg_clientes_k": ("Clientes activos", "Clientes que enviaron al menos una denuncia hace poco."),
        "neg_denuncias_k": ("Denuncias procesadas", "Denuncias analizadas entre todos los clientes."),
        "neg_ingreso": ("Ingreso del período", "La tarifa anual de cada cliente, repartida por los días."),
        "neg_costo": ("Costo de atender clientes", "IA, infraestructura y soporte de cada cliente."),
        "neg_margen": ("Ganancia sobre el ingreso", "Lo que queda del ingreso tras costos y la parte de Veridy (meta 60 %)."),
        "neg_utilidad": ("Utilidad", "Lo que queda al final, tras depreciación, interés e impuesto."),
        "neg_adopcion_k": ("Sugerencias calificadas", "Sugerencias que un auditor calificó, sobre el total (meta 50 %)."),
        "neg_sug": ("Denuncias con sugerencia", "De cada 100 denuncias, cuántas terminaron con sugerencia lista."),
        "neg_clientes": ("Clientes", "Cada fila: uso del plan, ingreso, costo y último uso del cliente."),
        "neg_clientes_uso": ("Clientes con y sin uso", "Clientes con contrato que ya enviaron denuncias y los que no."),
        "neg_denuncias": ("Denuncias por cliente", "Denuncias diarias de cada cliente, apiladas."),
        "neg_adopcion": ("Adopción", "De las denuncias, cuántas tuvieron sugerencia y calificación."),
        "neg_resultado": ("Del ingreso a la utilidad", "Cómo se pasa del ingreso a la utilidad, partida por partida."),
        "neg_supuestos": ("Supuestos", "Los supuestos del plan de negocio no se editan aquí."),
        "proyeccion": ("Proyección a 5 años", "Ingresos, costos y utilidad por año, según el plan de negocio."),
        "p_van": ("Ganancia a 5 años, en valor de hoy", "Lo que se espera ganar en 5 años, descontado a valor de hoy."),
        "p_tir": ("Rentabilidad anual del proyecto", "Lo que rinde la inversión cada año, en promedio."),
        "p_ind": ("Retorno por cada UF invertida", "UF que vuelven por cada UF invertida en el proyecto."),
        "p_rec": ("Año en que se recupera la inversión", "Primer año en que lo ganado cubre lo invertido."),
        "p_anillo": ("Reparto del ingreso del último año", "De cada 100 UF de ingreso del último año, cuántas quedan de utilidad."),
        "inf_veredicto": ("Veredicto", "Resume los indicadores clave: cuántos cumplen su meta."),
        "inf_serie": ("Acierto en las últimas mediciones", f"Cada punto es una medición; la línea punteada es la meta de {meta_r} %."),
        "inf_anon": ("Datos personales ocultados", "Qué datos personales detectó el anonimizador antes de enviar a la IA."),
        "inf_tokens": ("Texto procesado", "Texto que lee y escribe el modelo; con él se calcula el costo."),
        "inf_rent": ("Rentabilidad", "Lo que queda de cada cliente tras atenderlo, en UF."),
        "inf_incid": ("Incidentes", "Casos en revisión manual y fallas de proveedores, con su motivo."),
        "inf_datos": ("Datos", "Todas las tablas del informe; también están en Excel y CSV."),
        "inf_calidad": ("Calidad", "Acierto del artículo y de la ley sobre casos de prueba."),
        "inf_desempeno": ("Rapidez", "Tiempo que tarda cada etapa del análisis."),
        "inf_costo": ("Costos", "Costo de la IA por modelo y por denuncia."),
        "inf_resumen": ("Resumen", "Indicadores clave del período."),
        "aj_estado": ("¿Se aplica ya?", "«Activo» lo usa el conector ya; «Aún no» queda guardado para después."),
    }
    out = {k: {"t": t, "q": q, "c": "", "l": ""} for k, (t, q) in G.items()}
    out.update(_ajustes(L))
    out["ingresos_uf"] = {"t": "Ingresos (UF)", "q": "Lo que se espera facturar cada año, en UF, con los clientes esperados.", "c": "", "l": ""}
    return out
