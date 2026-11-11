"""Pruebas de las variantes del texto vectorizado y del manejo de la caché de resúmenes (sin red)."""
import json
import urllib.error

import pytest

import medir_variantes as m
import variantes_texto as v


def frag(texto, articulo="7", norma="Ley 20.393 Responsabilidad penal de las personas jurídicas",
         materias=("Personas Jurídicas", "Cohecho", "Ley no. 20.393"), parte="", fid="1008668-art-7"):
    return {"id": "x", "texto_embedding": "BASE " + texto,
            "payload": {"fragmento_id": fid, "norma": norma, "articulo": articulo, "texto": texto,
                        "materias": list(materias), "parte": parte, "tipo_numero": "Ley 20393"}}


T = "Artículo 7°.- Circunstancias agravantes. Constituyen circunstancias agravantes:\n\n1. La de haber sido condenada."


def test_separar_titulo_quita_prefijo_y_titulo():
    assert v.separar_titulo(T) == ("Circunstancias agravantes", "Constituyen circunstancias agravantes:\n\n1. La de haber sido condenada.")


@pytest.mark.parametrize("texto,prefijo", [
    ('"Artículo 1°.- Contenido de la ley. La presente ley regula', "La presente"),
    ("Artículo 16 bis.- Datos sensibles de salud. Si se cumple", "Si se cumple"),
    ("Art. 211-A.- Los trabajadores tienen derecho a que el empleador adopte medidas", "Los trabajadores"),
    ("Art.2.o Reconócese la función social que cumple el trabajo.", "Reconócese"),
    ("Artículo cuarto.- La primera designación de los consejeros del Consejo Directivo de la Agencia de Protección", "La primera"),
])
def test_cuerpo_empieza_en_el_contenido(texto, prefijo):
    assert v.separar_titulo(texto)[1].startswith(prefijo)


def test_sin_titulo_cuando_la_primera_frase_es_larga_o_termina_en_dos_puntos():
    assert v.separar_titulo("Art. 154. El reglamento interno deberá contener, a lo menos, lo siguiente:\n\n1.- horas.")[0] == ""
    largo = "Artículo 3.- " + "palabra " * 20 + "fin. Resto."
    assert v.separar_titulo(largo)[0] == ""


def test_nombre_corto():
    assert v.nombre_corto("Ley 20.393 Responsabilidad penal de las personas jurídicas") == "Responsabilidad penal de las personas jurídicas"
    assert v.nombre_corto("Ley 19.628 Protección de los datos personales (reformada por Ley 21.719)") == "Protección de los datos personales"
    assert v.nombre_corto("Ley 21.643 (Ley Karin) acoso laboral, sexual y violencia") == "Ley Karin: acoso laboral, sexual y violencia"
    assert v.nombre_corto("Código del Trabajo: artículos incorporados o modificados por la Ley 21.643 (Karin)") == "Código del Trabajo"


def test_materias_sin_etiqueta_de_ley_ni_repetidas_con_tope():
    mats = ["A", "Ley no. 19.628", "a", "B", "C", "D", "E", "F", "G"]
    assert v.materias_utiles(mats) == ["A", "B", "C", "D", "E", "F"]


def test_variante_a_encabezado_limpio_sin_articulo_repetido():
    a = v.variante_a(frag(T))
    enc, cuerpo = a.split("\n", 1)
    assert enc == ("Ley 20.393 (Responsabilidad penal de las personas jurídicas) · Art. 7 · Circunstancias agravantes"
                   " · Materias: Personas Jurídicas, Cohecho")
    assert cuerpo.startswith("Constituyen") and "Artículo 7" not in a and "Ley no." not in a


def test_variante_a_indica_la_parte():
    assert "Art. 2 (parte 1/2)" in v.encabezado_a(frag(T, articulo="2", parte="1/2"))


def test_variante_ab_inserta_resumen_entre_encabezado_y_texto():
    f = frag(T)
    ab = v.variante_ab(f, "  Quien comete delitos\n en la empresa. ")
    assert ab.split("\n", 1)[0] == v.encabezado_a(f)
    assert "\nResumen: Quien comete delitos" in ab and ab.endswith("condenada.")


def test_variante_ab_exige_resumen():
    with pytest.raises(ValueError):
        v.variante_ab(frag(T), "")


def test_construir_despacha_por_variante():
    f = frag(T)
    assert v.construir(f, "base") == "BASE " + T
    assert v.construir(f, "A") == v.variante_a(f)
    assert v.construir(f, "AB", {"1008668-art-7": "Resumen x."}) == v.variante_ab(f, "Resumen x.")
    with pytest.raises(ValueError):
        v.construir(f, "C")


def test_prompt_resumen_trae_norma_y_texto_sin_consultas():
    p = v.prompt_resumen(frag(T))
    assert "Ley 20.393" in p and "Circunstancias agravantes" in p and "lenguaje" in p


def test_limpiar_resumen():
    assert v.limpiar_resumen('"- Hola\n  mundo."') == "Hola mundo."
    largo = "Frase uno. " * 100
    r = v.limpiar_resumen(largo, 50)
    assert len(r) <= 50 and r.endswith(".")


# ---- caché y cobertura
def test_cobertura_y_resumenes_ignoran_vacios():
    frs = [frag(T, fid="a"), frag(T, fid="b")]
    cache = {"a": {"resumen": "x"}, "b": {"resumen": ""}}
    assert m.cobertura(frs, cache) == (1, 2) and m.resumenes_de(cache) == {"a": "x"}


def test_generar_resumenes_reutiliza_cache_y_se_detiene_sin_cuota():
    frs = [frag(T, fid=f) for f in "abc"]
    llamadas = []

    def gen(prompt):
        llamadas.append(1)
        if len(llamadas) == 2:
            raise urllib.error.HTTPError("u", 429, "cuota", {}, None)
        return "Resumen."

    guardados = []
    cache = m.generar_resumenes(frs, {"a": {"resumen": "previo"}}, generar=gen, pausa=0,
                                guardar=lambda c: guardados.append(json.dumps(c)))
    assert cache["a"]["resumen"] == "previo" and cache["b"]["resumen"] == "Resumen." and "c" not in cache
    assert m.cobertura(frs, cache) == (2, 3) and len(guardados) == 1


def test_coleccion_de_evaluacion_propia():
    assert m.coleccion_de("AB") == "normativa_cl_eval_te3l_varAB"
    assert m.coleccion_de("A") not in ("normativa_cl", "normativa_cl_local")
