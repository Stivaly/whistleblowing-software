"""Demo «Anonimizador» del panel: pasa un relato por el anonimizador de Kerna y devuelve lo que la página muestra.

El texto solo vive en memoria durante la petición: no se guarda, no se registra y no va a telemetría.
"""
from __future__ import annotations

from kerna_comun.anonimizador import anonimizar_detallado

MAX_CARACTERES = 5000

# Tipo de dato -> (nombre en singular, plural, color de categoría de la paleta B). El color de cada tipo es fijo en toda la sección.
TIPOS = {
    "PERSONA": ("Nombre", "Nombres", "violeta"),
    "RUT": ("RUT", "RUT", "azul"),
    "TELEFONO": ("Teléfono", "Teléfonos", "verde"),
    "CORREO": ("Correo", "Correos", "cian"),
    "DIRECCION": ("Dirección", "Direcciones", "naranja"),
    "PATENTE": ("Patente", "Patentes", "amarillo"),
    "CUENTA": ("Cuenta o tarjeta", "Cuentas o tarjetas", "coral"),
    "URL": ("Enlace", "Enlaces", "lima"),
}

RELATOS = (
    ("acoso", "Acoso en la oficina",
     "Me llamo Marcela Fuentes Araya, RUT 14.567.890-1, trabajo en la sucursal de Providencia. Desde marzo mi jefe directo, Rodrigo Valdés Contreras, "
     "me grita frente al equipo y me excluye de las reuniones. El 12 de octubre me dijo que si no \"colaboraba\" me iba a echar. Mi compañera Paola Núñez "
     "lo presenció. Puede escribirme a marcela.fuentes@gmail.com o llamarme al +56 9 8123 4567."),
    ("fraude", "Pagos a una empresa del jefe",
     "Soy contador en la empresa y detecté que la gerente de compras, doña Carolina Ibáñez Rojas, aprueba facturas a Servicios Lonquén SpA, cuyo dueño es su "
     "cuñado Felipe Araneda Soto (RUT 9.876.543-2). Las transferencias salen a la cuenta corriente 00123456789 del Banco de Chile. Tengo los correos en "
     "https://drive.grupoandina.cl/compras/2026. Pueden contactarme en el 2 2345 6789 o en el 9 7654 3210."),
    ("datos", "Datos de clientes en un grupo de WhatsApp",
     "En el área comercial se comparte una planilla con RUT, direcciones y teléfonos de clientes por un grupo de WhatsApp. El supervisor Andrés Poblete "
     "la reenvió a personas ajenas a la empresa. Ayer vi a un cliente, don Hernán Castillo Vera, RUT 7.654.321-K, reclamar porque lo llamaron al +56 2 2987 6543 "
     "ofreciéndole un crédito. Vive en Avenida Los Leones 1234, departamento 56, Ñuñoa. Mi correo es denunciante.reservado@outlook.com."),
    ("accidente", "Accidente sin reporte en la bodega",
     "El 3 de noviembre el conductor Luis Mardones Tapia, que maneja el camión patente KLRT-45, atropelló a un trabajador en la bodega de Pudahuel, calle Camino "
     "Lo Boza 2020. El jefe de turno, Sergio Bravo, ordenó no informarlo a la mutualidad. El accidentado, Jorge Pizarro Lagos (RUT 16.234.567-8), "
     "sigue con licencia. Yo soy bodeguera y prefiero no dar mi nombre; mi teléfono es 9 6543 2109."),
)


def _segmentos(texto: str, trozos: list) -> list:
    """Parte `texto` en [(fragmento, tipo o None, marcador o None)] según `trozos` = [(inicio, fin, tipo, marcador)] ordenados."""
    out, pos = [], 0
    for i, f, tipo, marcador in trozos:
        if i > pos:
            out.append((texto[pos:i], None, None))
        out.append((texto[i:f], tipo, marcador))
        pos = f
    if pos < len(texto):
        out.append((texto[pos:], None, None))
    return out


def analizar(texto: str) -> dict:
    """Devuelve lo que la página muestra: el original y el anonimizado con cada dato marcado por tipo, y el resumen por tipo.

    Una entidad es un valor distinto (la misma persona nombrada tres veces es una); una aparición es cada vez que se escribe.
    """
    texto = (texto or "").replace("\r\n", "\n").replace("\r", "\n")[:MAX_CARACTERES]
    res, entidades = anonimizar_detallado(texto)
    apariciones: dict = {}
    for _, _, tipo, _ in entidades:
        apariciones[tipo] = apariciones.get(tipo, 0) + 1
    # el mismo recorrido sobre el texto resultante: cada marcador ocupa su lugar
    nuevos, desplazamiento = [], 0
    for i, f, tipo, marcador in entidades:
        nuevos.append((i + desplazamiento, i + desplazamiento + len(marcador), tipo, marcador))
        desplazamiento += len(marcador) - (f - i)
    resumen = [{"tipo": t, "nombre": TIPOS[t][1] if res.conteos[t] != 1 else TIPOS[t][0], "color": TIPOS[t][2], "entidades": res.conteos[t],
                "apariciones": apariciones.get(t, 0)} for t in TIPOS if res.conteos.get(t)]
    ocultos = sum(f - i for i, f, _, _ in entidades)
    return {
        "texto": texto, "largo": len(texto), "anonimizado": res.texto,
        "original_seg": _segmentos(texto, entidades), "anonimizado_seg": _segmentos(res.texto, nuevos),
        "resumen": resumen, "total_entidades": sum(res.conteos.values()), "total_apariciones": len(entidades),
        "caracteres_ocultos": ocultos, "porcentaje_oculto": round(100 * ocultos / len(texto)) if texto else 0,
        "colores": {t: v[2] for t, v in TIPOS.items()},
    }
