"""Pruebas sin red de la herramienta que crea denuncias de prueba en Veridy."""
import json
from pathlib import Path

import pytest

from herramientas import crear_denuncias as cd

EJEMPLO = json.loads((Path(__file__).resolve().parents[1] / "datos" / "cuestionario_base_ejemplo.json").read_text(encoding="utf-8"))
CUEST, CTX = EJEMPLO["questionnaire"], EJEMPLO["context"]

CASO = {
    "id": "DEN-0001", "titulo": "Título de prueba", "resumen_parafraseado": "[Resumen parafraseado] Hecho resumido.",
    "submateria": "acoso", "ley_principal": "21.643", "texto_original": "DATO PERSONAL NO DEBE APARECER",
}


def _casos(n=30):
    leyes = ["21.643", "20.393", "19.628-21.719"]
    return [{"id": "DEN-%04d" % i, "ley_principal": leyes[i % 3]} for i in range(1, n + 1)]


@pytest.mark.pr("PR-13")
def test_relato_marca_y_sin_texto_original():
    r = cd.armar_relato(CASO)
    assert r.splitlines()[0] == "[PRUEBA SINTÉTICA DEN-0001]"
    assert "Título de prueba" in r and "Hecho resumido." in r and "acoso" in r
    assert "DATO PERSONAL" not in r and "[Resumen parafraseado]" not in r
    assert len(cd.armar_relato(dict(CASO, resumen_parafraseado="x" * 5000))) <= cd.MAX_RELATO


@pytest.mark.pr("PR-13")
def test_lote_determinista_y_variado():
    casos = _casos()
    a, b = cd.seleccionar_lote(casos, 6), cd.seleccionar_lote(list(reversed(casos)), 6)
    assert a == b and len(set(a)) == 6
    leyes = {c["id"]: c["ley_principal"] for c in casos}
    assert {leyes[i] for i in a} == {"21.643", "20.393", "19.628-21.719"}
    assert len(cd.seleccionar_lote(casos, 500)) == len(casos)


@pytest.mark.pr("PR-13")
def test_registro_idempotente(tmp_path):
    ruta = tmp_path / "reg.json"
    r = cd.Registro(ruta)
    assert r.anotar("DEN-0001", "1234567890123456") is True
    assert r.anotar("DEN-0001", "0000000000000000") is False
    r2 = cd.Registro(ruta)
    assert "DEN-0001" in r2 and r2.datos["DEN-0001"]["recibo"] == "1234567890123456"
    assert r2.datos["DEN-0001"]["fecha_utc"].endswith("+00:00")
    r2.actualizar_id("DEN-0001", "abc")
    assert cd.Registro(ruta).datos["DEN-0001"]["denuncia_id"] == "abc"
    r2.descartar("DEN-0001")
    assert "DEN-0001" not in cd.Registro(ruta)


@pytest.mark.pr("PR-13")
def test_cuerpo_con_cuestionario_de_ejemplo():
    ans = cd.armar_respuestas(CUEST, cd.armar_relato(CASO), "21.643")
    assert cd.validar_cuerpo(CUEST, ans) == []
    campos = {c["id"]: c for s in CUEST["steps"] for c in s["children"]}
    assert set(ans) == set(campos)
    for cid, c in campos.items():
        if c["type"] == "textarea":
            assert ans[cid][0]["value"].startswith("[PRUEBA SINTÉTICA")
        if c["type"] == "fileupload" or c["label"].startswith("Indica la forma"):
            assert ans[cid] == [{}]  # no activados con "No me es posible proporcionar evidencias"
    tipo = next(c for c in campos.values() if c["label"] == "Tipo de denuncia")
    assert ans[tipo["id"]][0]["value"] == tipo["options"][0]["id"]
    comparte = next(c for c in campos.values() if c["label"].startswith("¿Desea compartir"))
    no = next(o for o in comparte["options"] if o["label"] == "No")
    assert ans[comparte["id"]][0]["value"] == no["id"]

    cuerpo = cd.armar_cuerpo(CTX, ans, "x" * 44)
    assert set(cuerpo) == {"context_id", "receivers", "identity_provided", "answers", "score", "receipt"}
    assert cuerpo["identity_provided"] is False and cuerpo["score"] == 0
    assert cuerpo["receivers"] == CTX["receivers"]
    json.dumps(cuerpo)


@pytest.mark.pr("PR-13")
def test_validar_detecta_obligatorio_vacio():
    ans = cd.armar_respuestas(CUEST, "relato")
    nombres = next(c for s in CUEST["steps"] for c in s["children"] if c["label"] == "Nombres")
    ans[nombres["id"]] = [{"value": ""}]
    assert cd.validar_cuerpo(CUEST, ans)


@pytest.mark.pr("PR-13")
def test_recibo_formato():
    r = cd.generar_recibo()
    assert len(r) == 16 and r.isdigit()
