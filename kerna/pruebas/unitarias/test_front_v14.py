"""Front v14: Negocio e Informe con el lenguaje de bandas del Resumen, anillos, nombres de indicadores que se entienden solos y «?» de una línea."""
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
from test_front_rediseno import H, inf  # noqa: E402,F401
from app import cache, glosario, negocio, principal  # noqa: E402

EST = Path(__file__).resolve().parents[2] / "front" / "app"
CSS = (EST / "estaticos" / "kerna.css").read_text()
JS = (EST / "estaticos" / "kerna.js").read_text()
VIEJOS = ("Valoradas", "Índice de rentabilidad", "Valor actual neto", "Margen operativo", "Costo de servir", "Retorno anual")


def _negocio(monkeypatch):
    cli_ = [{"PartitionKey": "a", "nombre": "Cliente A", "plan_tipo": "basico", "plan_denuncias_mes": 150, "estado": "activo"},
            {"PartitionKey": "b", "nombre": "Cliente B", "plan_tipo": "pro", "plan_denuncias_mes": 300, "estado": "activo"}]
    n = negocio.construir(cli_, [], dias=30)
    monkeypatch.setattr(principal.negocio, "cargar", lambda **k: n)
    return TestClient(principal.app, base_url="https://t").get("/panel/negocio", headers=H).text


def test_los_tooltips_son_de_una_linea():
    g = glosario.glosario()
    largos = {k: len(v["q"]) for k, v in g.items() if len(v["q"]) > 80}
    assert not largos, largos
    assert all(not v["c"] and not v["l"] for v in g.values())
    assert "tt.textContent" in JS and "innerHTML = '<b>'" not in JS


def test_negocio_usa_bandas_con_anillos_y_columnas(monkeypatch):
    h = _negocio(monkeypatch)
    for c in ("zv", "z-pr", "z-kb", "z-ly", "z-cm", "pr-n", "py-g", "py-k", 'class="dn"'):
        assert c in h, c
    assert h.count('class="dn-a"') >= 2                       # un anillo de clientes y otro del ingreso del último año


def test_negocio_nombres_que_se_entienden_solos(monkeypatch):
    h = _negocio(monkeypatch)
    visibles = re.sub(r"<script.*?</script>", "", h, flags=re.S)
    for viejo in VIEJOS:
        assert re.search(r">\s*" + re.escape(viejo) + r"\s*<", visibles) is None or viejo == "Margen operativo", viejo
    for nuevo in ("Ganancia sobre el ingreso", "Costo de atender clientes", "Denuncias con sugerencia", "Sugerencias calificadas", "Ganancia a 5 años, valor de hoy",
                  "Rentabilidad anual del proyecto", "Retorno por cada UF invertida", "Recuperas la inversión en"):
        assert nuevo in h, nuevo


def test_informe_sin_tarjetas_de_borde_de_color_y_con_anillos(inf):
    cache.vaciar()
    cache._datos[("informe", 30, None, None)] = (__import__("time").time(), inf)
    t = TestClient(principal.app, base_url="https://t").get("/panel/informe?dias=30", headers=H).text
    assert 'class="zv"' in t and "z-kb" in t and re.search(r'class="stl s-\w+"', t) and 'class="ani"' in t
    assert not re.search(r"border-left:4px[^}]*var\(--sc\)", CSS.split("/* v14")[-1])


def test_pestanas_del_informe_con_bandas_de_color(inf):
    cache.vaciar()
    cache._datos[("informe", 30, None, None)] = (__import__("time").time(), inf)
    t = TestClient(principal.app, base_url="https://t").get("/panel/informe?dias=30", headers=H).text
    assert len(re.findall(r'class="tp bn z-\w+"', t)) == 6


def test_el_signo_de_ayuda_de_la_cola_queda_junto_al_texto():
    assert re.search(r"\.cola>\.mk\{display:block", CSS)


def test_todos_los_tooltips_usados_existen_en_el_glosario():
    g = glosario.glosario()
    usados = set()
    for p in (EST / "plantillas").glob("*.html"):
        usados |= set(re.findall(r"tip\('(\w+)'", p.read_text()))
    usados |= set(re.findall(r'"g": "(\w+)"', (EST / "vistas.py").read_text()))
    assert usados - set(g) == set()


def test_clases_nuevas_de_negocio_no_chocan_con_las_existentes():
    html = (EST / "plantillas" / "negocio.html").read_text()
    for c in ("cli-s", "cli-g", "cli-l", "cli-d", "pr-n", "py-g", "py-k", "py-d", "py-c"):
        assert c in html
        assert len(re.findall(r"\." + c + r"[{ ,.:>]", CSS)) >= 1 or c in ("cli-s", "cli-l", "py-c")
    # los nombres viejos (cl-*, cn-n) ya usados por otras reglas del CSS no se reutilizan
    assert not re.search(r'class="[^"]*\b(cl-[gldn]|cn-n)\b', html)
