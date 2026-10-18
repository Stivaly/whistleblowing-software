"""Pruebas del acceso temporal a Atlas y de su uso en run.sh, sin llamar a la API."""
import os
import subprocess
from pathlib import Path

import pytest

import atlas_acceso as a


class AtlasFalso:
    def __init__(self, entradas=None, estados=("PENDING", "ACTIVE")):
        self.entradas = dict(entradas or {})
        self.estados = list(estados)
        self.llamadas = []

    def __call__(self, metodo, ruta, cuerpo=None):
        self.llamadas.append((metodo, ruta, cuerpo))
        if ruta.endswith("/status"):
            return 200, {"STATUS": self.estados.pop(0)}
        if metodo == "POST":
            for e in cuerpo:
                self.entradas[e["ipAddress"]] = e
            return 201, {}
        ip = ruta.rsplit("/", 1)[1]
        if metodo == "GET":
            return (200, self.entradas[ip]) if ip in self.entradas else (404, {})
        if metodo == "DELETE":
            return (204, {}) if self.entradas.pop(ip, None) else (404, {})


@pytest.fixture
def atlas(monkeypatch, tmp_path):
    falso = AtlasFalso()
    monkeypatch.setattr(a, "_pedir", falso)
    monkeypatch.setattr(a, "ESTADO", str(tmp_path / "atlas.json"))
    monkeypatch.setattr(a, "ip_salida", lambda: "20.1.2.3")
    monkeypatch.setattr(a.time, "sleep", lambda n: None)
    return falso


def test_abrir_agrega_entrada_con_vencimiento_y_espera_activa(atlas):
    a.abrir()
    post = [c for c in atlas.llamadas if c[0] == "POST"]
    [[entrada]] = [c[2] for c in post]
    assert entrada["ipAddress"] == "20.1.2.3"
    assert entrada["deleteAfterDate"].endswith("Z") and entrada["comment"].startswith("kerna job ")
    assert [c[1] for c in atlas.llamadas].count("/accessList/20.1.2.3/status") == 2

    a.cerrar()
    assert ("DELETE", "/accessList/20.1.2.3", None) in atlas.llamadas
    assert "20.1.2.3" not in atlas.entradas
    a.cerrar()  # repetir no vuelve a borrar
    assert [c[0] for c in atlas.llamadas].count("DELETE") == 1


def test_no_toca_una_entrada_permanente(atlas):
    atlas.entradas["20.1.2.3"] = {"ipAddress": "20.1.2.3", "comment": "host"}
    a.abrir()
    a.cerrar()
    assert [c[0] for c in atlas.llamadas] == ["GET"]
    assert "20.1.2.3" in atlas.entradas


def test_falla_si_la_entrada_no_queda_activa(atlas):
    atlas.estados = ["FAILED"]
    with pytest.raises(RuntimeError):
        a.abrir()
    a.cerrar()  # el trap de run.sh la quita igual
    assert "20.1.2.3" not in atlas.entradas


def test_cerrar_sin_abrir_no_hace_nada(atlas):
    a.cerrar()
    assert atlas.llamadas == []


@pytest.fixture
def python_falso(tmp_path):
    """`python` falso para run.sh: registra cada llamada y hace fallar el extractor."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    registro = tmp_path / "llamadas.txt"
    (bin_ / "python").write_text(f'#!/bin/sh\necho "$*" >> {registro}\n[ "$1" != extraer_bcn.py ]\n')
    (bin_ / "python").chmod(0o755)
    return bin_, registro


def correr(modo, entorno, python_falso):
    bin_, registro = python_falso
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", **entorno}
    r = subprocess.run(["sh", "run.sh", modo], cwd=Path(__file__).parent, env=env, capture_output=True)
    return r.returncode, registro.read_text().splitlines() if registro.exists() else []


def test_run_sh_abre_y_cierra_atlas_aunque_falle(python_falso):
    rc, llamadas = correr("diario", {"ATLAS_ACCESO_TEMPORAL": "1"}, python_falso)
    assert llamadas == ["atlas_acceso.py abrir", "extraer_bcn.py", "atlas_acceso.py cerrar"]
    assert rc == 1  # conserva el código de error del pipeline


def test_run_sh_sin_atlas_temporal(python_falso):
    rc, llamadas = correr("embed", {"ATLAS_ACCESO_TEMPORAL": "0"}, python_falso)
    assert llamadas == ["embed_sync.py"] and rc == 0
