"""Lugar único de los ajustes de Kerna: valores por defecto, rangos, opciones y validación.

Python puro, sin dependencias: lo importan el front (panel Ajustes), el conector y el núcleo.
Los valores guardados viven en la tabla `ajustes` (fila kerna/actual, JSON en `valores`).
"""
from __future__ import annotations

DEFECTOS = {
    "envios": 5, "reintentos": 3, "espera": 24, "revision": 30, "reprocesar": False,
    "evaluador": True, "candidatos": 70,
    "cadena": [{"v": "azure", "on": True}, {"v": "gemini", "on": True}],
    "compartir": ["analista"], "maxresp": 15, "alerta": 6,
}

RANGOS = {  # min, max, step
    "envios": {"min": 1, "max": 10, "step": 1},
    "reintentos": {"min": 0, "max": 5, "step": 1},
    "candidatos": {"min": 10, "max": 70, "step": 10},
    "maxresp": {"min": 5, "max": 60, "step": 5},
}

OPCIONES = {  # ajustes de selección única
    "espera": (6, 12, 24, 48),
    "revision": (15, 30, 60, 300),
    "alerta": (1, 6, 24),
}

EQUIPOS = {
    "analista": {"etiqueta": "Analistas de cumplimiento", "receptor": "Auditor Kerna"},
    "comite": {"etiqueta": "Comité de ética", "receptor": "kerna-equipo-comite"},
    "auditoria": {"etiqueta": "Auditoría interna", "receptor": "kerna-equipo-auditoria"},
    "legal": {"etiqueta": "Fiscalía legal", "receptor": "kerna-equipo-legal"},
}

PROVEEDOR_DE = {"azure": "azure-openai", "gemini": "gemini"}
SWITCHES = ("reprocesar", "evaluador")


def validar(v: dict) -> dict:
    """Devuelve los valores limpios (tipos y rangos); lanza ValueError si algo no es válido."""
    out = {}
    for k, defecto in DEFECTOS.items():
        x = v.get(k, defecto)
        if k in SWITCHES:
            if not isinstance(x, bool):
                raise ValueError(k)
        elif k in RANGOS:
            r = RANGOS[k]
            if isinstance(x, bool) or not isinstance(x, int) or not r["min"] <= x <= r["max"] or (x - r["min"]) % r["step"]:
                raise ValueError(k)
        elif k in OPCIONES:
            if isinstance(x, bool) or x not in OPCIONES[k]:
                raise ValueError(k)
        elif k == "compartir":
            if not isinstance(x, list) or any(e not in EQUIPOS for e in x) or len(set(x)) != len(x):
                raise ValueError(k)
        elif k == "cadena":
            if (not isinstance(x, list) or any(not isinstance(m, dict) for m in x)
                    or sorted(m.get("v") for m in x) != sorted(PROVEEDOR_DE)
                    or any(not isinstance(m.get("on"), bool) for m in x)
                    or not any(m["on"] for m in x)):
                raise ValueError(k)
            x = [{"v": m["v"], "on": m["on"]} for m in x]
        out[k] = x
    return out
