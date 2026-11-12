#!/usr/bin/env python3
"""Lámina de todos los íconos de identidad que usa el front y dónde se usan. Genera un HTML que lamina_iconos.sh captura como prod6-iconos.png.
Uso: python3 lamina_iconos.py <salida.html>   (la salida debe estar en kerna/front/herramientas/ para que las rutas relativas sirvan)"""
import sys
from pathlib import Path
from construir_identidad import ICONOS, NUEVOS, LEY

EST = "../app/estaticos"
ESTADO_TXT = {"lista": "Sugerencia lista", "generando": "Preparando", "contingencia-modelo": "Modo alternativo", "contingencia-busqueda": "Búsqueda alternativa",
              "revision-citas": "Citas no verificadas", "revision-tiempo": "Tiempo excedido", "cadena-agotada": "No se pudo", "nucleo-no-disponible": "No disponible",
              "sin-info": "Sin información", "sin-conexion": "Sin conexión", "sin-normativa": "Sin normativa", "conector-en-proceso": "Recibido, sin respuesta",
              "conector-sin-nota": "Sin respuesta", "valorada": "Clasificación guardada"}
USO_E = {"lista": "veredicto del informe; proveedor operativo; modo principal; indicadores en meta", "generando": "estado en proceso",
         "contingencia-modelo": "bloque de reintentos; modo de respaldo; indicadores con atención", "contingencia-busqueda": "búsqueda de leyes (salud)",
         "revision-citas": "revisión manual por citas", "revision-tiempo": "análisis fuera de plazo (reintentos)", "cadena-agotada": "indicadores fuera de meta; fallas",
         "nucleo-no-disponible": "modelos de IA no disponibles (reintentos)", "sin-info": "estados vacíos «sin información»", "sin-conexion": "proveedor sin información",
         "sin-normativa": "sin normativa aplicable", "conector-en-proceso": "enlace con Veridy en proceso", "conector-sin-nota": "enlace sin respuesta",
         "valorada": "Valoradas (Negocio); clasificación guardada"}
USO_N = {"resumen": "menú Resumen", "informe": "menú y pestañas del informe", "negocio": "menú Negocio", "ajustes": "menú Ajustes", "portada": "ver portada pública",
         "denuncias": "indicador Denuncias", "acierto": "indicador Acierto", "tiempo": "indicador Respuesta; pestaña Rapidez", "costo": "indicador Costo; pestaña Costos",
         "ingresos": "indicador Ingreso", "utilidad": "indicador Utilidad", "margen": "indicador Margen operativo", "clientes": "indicador Clientes activos",
         "modelo": "modelos de IA; ajustes de modelos", "ayuda": "«?» de cada título", "descargar": "botón Informe y descargas", "reintentar": "Reintentar ahora",
         "restaurar": "Valores recomendados", "calendario": "Otro período", "tabla": "pestaña Datos; CSV y Excel", "editar": "ajuste cambiado", "guardar": "barra Guardar",
         "persona": "Compartir con", "flujo": "Ajustes: Procesamiento", "ia": "Ajustes: Inteligencia artificial", "plazos": "Ajustes: Plazos"}
USO_L = {"karin": "Ley 21.643: acierto por ley, leyes sugeridas, cobertura", "datos": "Ley 19.628 y 21.719", "penal": "Ley 20.393"}
NOM_L = {"karin": "Ley Karin", "datos": "Datos personales", "penal": "Responsabilidad penal"}


def u(i, w, h=None):
    return f'<svg width="{w}" height="{h or w}"><use href="{EST}/identidad.svg#{i}"/></svg>'


CSS = ('body{background:#fff;padding:24px;font:13px Inter,sans-serif;margin:0;width:1500px}h1{font:700 26px Unbounded;margin:0 0 4px;color:#1C2A6B}'
       'h2{font:600 12px "JetBrains Mono",monospace;letter-spacing:.14em;text-transform:uppercase;margin:22px 0 10px;color:#4F5B85}'
       '.g{display:grid;grid-template-columns:repeat(6,1fr);gap:14px}.c{display:grid;gap:4px;justify-items:start;align-content:start}'
       '.c b{font:700 10.5px "JetBrains Mono",monospace;letter-spacing:.08em;text-transform:uppercase}.c span{color:#4F5B85;font-size:11.5px;line-height:1.3}'
       '.g2{display:grid;grid-template-columns:repeat(9,1fr);gap:14px}.row{display:flex;gap:10px;align-items:center}.ti{display:block;line-height:0}')
h = [f'<!doctype html><meta charset=utf-8><link rel=stylesheet href="{EST}/kerna.css"><style>{CSS}</style>',
     '<h1>Kerna · íconos de identidad Núcleo en el front</h1><p style="margin:0;color:#4F5B85">Baldosas de estado, íconos de ley y íconos propios con el mismo lenguaje (trazo, órbita, satélite, núcleo). Fondo claro, paleta B.</p>',
     '<h2>Estados (baldosas grandes) y dónde se usan</h2><div class="g">']
for n in ICONOS:
    h.append(f'<div class="c"><div class="ti" data-e="{n}">{u("t-" + n, 150, 112)}</div><b>{ESTADO_TXT[n]}</b><span>{USO_E[n]}</span></div>')
h.append('</div><h2>Estados en tarjetas (44 px) y en listas densas (20 px)</h2><div class="g2">')
for n in ICONOS:
    h.append(f'<div class="c"><div class="row"><k-st data-e="{n}" style="--s:44px">{u("e-" + n, 44)}</k-st><k-st data-e="{n}" class="sm" style="--s:20px">{u("m-" + n, 20)}</k-st></div></div>')
h.append('</div><h2>Leyes</h2><div class="g">')
for n in LEY:
    h.append(f'<div class="c"><div class="lx" data-l="{n}">{u("l-" + n, 64)}</div><b>{NOM_L[n]}</b><span>{USO_L[n]}</span></div>')
h.append('</div><h2>Íconos propios nuevos (mismo lenguaje)</h2><div class="g2">')
for n in NUEVOS:
    h.append(f'<div class="c"><k-n>{u("n-" + n, 56)}</k-n><b>{n}</b><span>{USO_N.get(n, "")}</span></div>')
h.append("</div>")
Path(sys.argv[1]).write_text("".join(h))
