import json

import traductor
from tests.fakes import ClienteFalso


def test_traduce_en_su_lugar(monkeypatch):
    monkeypatch.undo()
    arts = [{"titulo": "El Salvador signs deal"}, {"titulo": "Bukele meets Trump"}]
    traductor.traducir(arts, client=ClienteFalso(json.dumps(["El Salvador firma acuerdo", "Bukele se reúne con Trump"])))
    assert [a["titulo"] for a in arts] == ["El Salvador firma acuerdo", "Bukele se reúne con Trump"]


def test_si_falla_quedan_los_originales(monkeypatch):
    monkeypatch.undo()
    arts = [{"titulo": "A"}, {"titulo": "B"}]
    traductor.traducir(arts, client=ClienteFalso(json.dumps(["solo uno"])))
    assert [a["titulo"] for a in arts] == ["A", "B"]


def test_sin_clave_no_falla(monkeypatch):
    monkeypatch.undo()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    arts = [{"titulo": "A"}]
    traductor.traducir(arts)
    assert arts[0]["titulo"] == "A"
