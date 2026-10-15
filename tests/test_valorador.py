import pytest

import valorador
from tests.fakes import N1, ClienteFalso


def test_valoraciones_parseadas():
    c = ClienteFalso('Aquí va: [{"titulo": "Remesas crecen 5%", "valoracion": "L1. L2."}]')
    assert valorador.generar_valoraciones([N1], client=c) == [{"titulo": "Remesas crecen 5%", "valoracion": "L1. L2."}]
    assert "centroamericanas" in c.prompts[0] and c.modelos == ["gemini-2.5-flash-lite"]


def test_reintento_unico_y_error():
    c = ClienteFalso("nada", "tampoco")
    with pytest.raises(RuntimeError):
        valorador.generar_valoraciones([N1], client=c)
    assert len(c.prompts) == 2


def test_vacio():
    assert valorador.generar_valoraciones([]) == []
