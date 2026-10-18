import pytest

import guionista
from tests.fakes import GUION_OK, N1, N2, ClienteFalso


def test_prompt_incluye_fuentes_paises_e_instrucciones():
    c = ClienteFalso(GUION_OK)
    guionista.generar_guion([N1, N2], instrucciones="SALUDO-PROPIO", client=c)
    p = c.prompts[0]
    for esperado in ("Remesas crecen 5%", "La Prensa Gráfica", "Prensa Libre", "El Salvador", "Guatemala",
                     "SALUDO-PROPIO", "[APERTURA]", "[CIERRE]"):
        assert esperado in p


def test_resultado_con_palabras_y_minutos():
    r = guionista.generar_guion([N1], instrucciones="x", client=ClienteFalso(GUION_OK))
    assert r["texto"] == GUION_OK and r["palabras"] == 12 and r["minutos"] == 0.1


def test_contar_palabras_excluye_marcas():
    assert guionista.contar_palabras("[APERTURA]\nHola a todos\n[CIERRE]\nAdiós") == 4


def test_minutos_150_ppm():
    assert guionista.minutos_estimados(300) == 2.0
    assert guionista.minutos_estimados(500) == 3.3


def test_sin_noticias_o_mas_de_12_lanza():
    with pytest.raises(ValueError):
        guionista.generar_guion([], client=ClienteFalso())
    with pytest.raises(ValueError):
        guionista.generar_guion([N1] * 13, client=ClienteFalso())


def test_reintenta_si_faltan_marcas():
    c = ClienteFalso("texto sin marcas", GUION_OK)
    assert guionista.generar_guion([N1], instrucciones="x", client=c)["texto"] == GUION_OK
    assert len(c.prompts) == 2


def test_usa_modelo_de_guion():
    c = ClienteFalso(GUION_OK)
    guionista.generar_guion([N1], instrucciones="x", client=c)
    assert c.modelos == ["gemini-2.5-flash"]


def test_instrucciones_por_defecto_desde_archivo():
    c = ClienteFalso(GUION_OK)
    guionista.generar_guion([N1], client=c)
    assert "Guion de Medios" in c.prompts[0]


def test_sin_clave_lanza_config_error(monkeypatch):
    import ia
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ia.ConfigError):
        guionista.generar_guion([N1], instrucciones="x")


def test_notas_de_apoyo_no_cuentan_como_palabras_habladas():
    texto = "[APERTURA]\nHola a todos\n[CIERRE]\nAdiós\n[NOTAS DE APOYO]\nDato: remesas, LPG, 14/10/2026"
    assert guionista.contar_palabras(texto) == 4


def test_prompt_pide_analisis_fechas_y_notas():
    c = ClienteFalso(GUION_OK)
    guionista.generar_guion([N1], instrucciones="x", client=c)
    p = c.prompts[0]
    assert "[NOTAS DE APOYO]" in p and "Fecha: 14/10/2026" in p and "Gobierno de El Salvador" in p


def test_guion_largo_se_acorta():
    largo = "[APERTURA]\n" + "palabra " * 900 + "\n[CIERRE]\nAdiós"
    c = ClienteFalso(largo, GUION_OK)
    r = guionista.generar_guion([N1], instrucciones="x", client=c)
    assert r["texto"] == GUION_OK and "Acórtalo" in c.prompts[1]
