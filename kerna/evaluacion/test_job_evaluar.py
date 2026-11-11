"""Coherencia entre el job de Azure y recall_retriever.py (sin red ni modelos)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "job_embeddings"))
import evaluar as ev  # noqa: E402
import recall_retriever as r  # noqa: E402


@pytest.mark.pr("PR-01")
def test_clave_y_texto_de_consulta_coinciden_con_el_recuperador():
    caso = {"texto_original": " Jefe acosa. ", "resumen_parafraseado": "[Resumen parafraseado] Resumen."}
    for campo in ("texto_original", "resumen_parafraseado"):
        assert ev.texto_consulta(caso, campo) == r.texto_consulta(caso, campo)
    assert ev.clave_texto("hola") == r.clave_texto("hola")


@pytest.mark.pr("PR-01")
def test_normalizar_trunca_y_normaliza():
    v = ev.normalizar([3.0, 4.0] + [0.0] * 5000)
    assert len(v) == 1024 and v[0] == pytest.approx(0.6) and v[1] == pytest.approx(0.8)
    assert len(ev.normalizar([1.0] * 768)) == 768


@pytest.mark.pr("PR-01")
def test_vectores_externos_desde_archivo(tmp_path):
    import json
    ref = tmp_path / "c.json"
    ref.write_text(json.dumps({"consultas": {r.clave_texto("a"): {"vector": [1.0], "ms": 5.0, "tokens": 3}}}))
    assert r.cargar_vectores_externos(str(ref), ["a"]) == ([[1.0]], [5.0], [3])
    with pytest.raises(RuntimeError):
        r.cargar_vectores_externos(str(ref), ["a", "b"])


def test_config_modelos_incluye_los_cuatro():
    assert {"embeddinggemma-300m", "bge-m3", "multilingual-e5-large-instruct", "qwen3-embedding-8b"} <= set(ev.CONFIG)
    assert ev.CONFIG["multilingual-e5-large-instruct"]["consulta"].startswith("Instruct: ")
