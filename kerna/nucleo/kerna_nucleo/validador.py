"""Validación de citas de la generación contra los fragmentos recuperados."""
from __future__ import annotations

import re
import unicodedata

MIN_CITA = 10

_COMILLAS = {"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'",
             "‚": "'", "‹": "'", "›": "'", "`": "'", "´": "'"}


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKC", texto or "")
    t = "".join(_COMILLAS.get(c, c) for c in t)
    return re.sub(r"\s+", " ", t).strip().lower()


def validar(candidatos: list[dict], fragmentos: list[dict], max_articulos: int = 5):
    """Devuelve (aceptados, rechazados). Cada aceptado es {"fragmento": dict, "explicacion", "cita", "confianza"};
    cada rechazado, {"fragmento_id", "motivo"} con motivo: inexistente | no_vigente | cita_no_literal | duplicado | invalido."""
    por_id = {f.get("fragmento_id"): f for f in fragmentos}
    aceptados, rechazados, vistos = [], [], set()
    for c in candidatos or []:
        if not isinstance(c, dict):
            rechazados.append({"fragmento_id": "", "motivo": "invalido"})
            continue
        fid = c.get("fragmento_id")
        frag = por_id.get(fid) if isinstance(fid, str) else None
        if frag is None:
            rechazados.append({"fragmento_id": str(fid)[:64], "motivo": "inexistente"})
        elif frag.get("vigente") is not True:
            rechazados.append({"fragmento_id": fid, "motivo": "no_vigente"})
        elif fid in vistos:
            rechazados.append({"fragmento_id": fid, "motivo": "duplicado"})
        else:
            cita = c.get("cita")
            nc = normalizar(cita) if isinstance(cita, str) else ""
            try:
                conf = max(0.0, min(1.0, float(c.get("confianza", 0))))
            except (TypeError, ValueError):
                conf = -1
            expl = c.get("explicacion")
            if len(nc) < MIN_CITA or nc not in normalizar(frag.get("texto", "")):
                rechazados.append({"fragmento_id": fid, "motivo": "cita_no_literal"})
            elif conf < 0 or not isinstance(expl, str) or not expl.strip():
                rechazados.append({"fragmento_id": fid, "motivo": "invalido"})
            else:
                vistos.add(fid)
                aceptados.append({"fragmento": frag, "explicacion": expl.strip(), "cita": cita.strip(),
                                  "confianza": conf})
    aceptados.sort(key=lambda a: a["confianza"], reverse=True)
    return aceptados[:max_articulos], rechazados
