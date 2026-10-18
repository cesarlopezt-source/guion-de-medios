import json

import pytest

import brief
from tests.fakes import N1, N2, ClienteFalso

RESPUESTA = json.dumps({"analisis": "Panorama del día.", "briefs": [{"n": 1, "brief": "B1"}, {"n": 2, "brief": "B2"}]})


def test_ambos_trae_analisis_briefs_y_enlaces():
    texto = brief.generar_brief([N1, N2], "ambos", client=ClienteFalso(RESPUESTA))["texto"]
    assert texto.startswith("[ANÁLISIS GENERAL]\nPanorama del día.")
    assert "[1 · El Salvador]\nRemesas crecen 5%\nB1\n- La Prensa Gráfica: https://lpg/1" in texto
    assert "[2 · Guatemala]\nExportaciones de café\nB2\n- Prensa Libre: https://pl/2" in texto


def test_solo_brief_sin_analisis():
    texto = brief.generar_brief([N1], "brief", client=ClienteFalso(RESPUESTA))["texto"]
    assert "ANÁLISIS" not in texto and "B1" in texto


def test_solo_analisis_sin_noticias():
    texto = brief.generar_brief([N1], "analisis", client=ClienteFalso(RESPUESTA))["texto"]
    assert texto == "[ANÁLISIS GENERAL]\nPanorama del día."


def test_reintenta_si_no_es_json():
    c = ClienteFalso("no es json", RESPUESTA)
    assert "B1" in brief.generar_brief([N1], "brief", client=c)["texto"]
    assert len(c.prompts) == 2


def test_validaciones():
    with pytest.raises(ValueError):
        brief.generar_brief([], "brief", client=ClienteFalso())
    with pytest.raises(ValueError):
        brief.generar_brief([N1] * 41, "brief", client=ClienteFalso())
    with pytest.raises(ValueError):
        brief.generar_brief([N1], "otro", client=ClienteFalso())
