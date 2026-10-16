import pytest
from google.genai import errors

import ia


class ClienteSaturado:
    """Falla con el código indicado para los modelos de `fallan`; responde 'ok <modelo>' a los demás."""

    def __init__(self, fallan, codigo=503):
        # fallan: conjunto de modelos (todos con `codigo`) o dict modelo → código
        self.fallan = fallan if isinstance(fallan, dict) else {m: codigo for m in fallan}
        self.modelos = []
        self.models = self

    def generate_content(self, model, contents):
        self.modelos.append(model)
        if model in self.fallan:
            codigo = self.fallan[model]
            raise errors.APIError(codigo, {"error": {"code": codigo, "message": "high demand",
                                                          "status": "UNAVAILABLE"}})
        return type("R", (), {"text": f"ok {model}"})()


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    monkeypatch.setattr(ia, "_dormir", lambda s: None)


def test_saturado_reintenta_y_pasa_al_modelo_de_respaldo():
    c = ClienteSaturado({"principal"})
    assert ia.generar("p", "principal", c, respaldos=["respaldo"]) == "ok respaldo"
    assert c.modelos == ["principal", "principal", "respaldo"]


def test_todos_saturados_da_mensaje_claro():
    c = ClienteSaturado({"principal", "respaldo"})
    with pytest.raises(ia.IASaturada, match="saturado"):
        ia.generar("p", "principal", c, respaldos=["respaldo"])


def test_error_que_no_es_de_saturacion_no_se_reintenta():
    c = ClienteSaturado({"principal"}, codigo=400)
    with pytest.raises(errors.APIError):
        ia.generar("p", "principal", c, respaldos=["respaldo"])
    assert c.modelos == ["principal"]


def test_respaldo_inexistente_se_salta():
    c = ClienteSaturado({"principal": 503, "no-existe": 404})
    assert ia.generar("p", "principal", c, respaldos=["no-existe", "respaldo"]) == "ok respaldo"
    assert c.modelos == ["principal", "principal", "no-existe", "respaldo"]


def test_respaldos_por_defecto_vienen_de_ajustes():
    import ajustes
    assert ajustes.GEMINI_RESPALDOS and "gemini-2.5-flash" not in ajustes.GEMINI_RESPALDOS
