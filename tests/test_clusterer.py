from datetime import datetime, timedelta, timezone

from clusterer import agrupar

T0 = datetime(2026, 10, 10, tzinfo=timezone.utc)


def a(titulo, horas=0):
    return {"titulo": titulo, "publicado": T0 + timedelta(hours=horas)}


def test_agrupa_titulos_similares():
    g = agrupar([a("Remesas crecen 5% en septiembre"), a("Remesas crecen 5% en septiembre 2026"), a("Otra cosa distinta")])
    assert sorted(len(c) for c in g) == [1, 2]


def test_no_agrupa_fuera_de_ventana_48h():
    g = agrupar([a("Remesas crecen 5% en septiembre"), a("Remesas crecen 5% en septiembre", horas=120)])
    assert len(g) == 2


def test_agrupa_dentro_de_ventana_sin_importar_orden():
    g = agrupar([a("Presupuesto 2027 llega a la Asamblea", 40), a("Presupuesto 2027 llega a la Asamblea", 0)])
    assert len(g) == 1


def test_vacio():
    assert agrupar([]) == []


def test_titulos_con_pocas_palabras_en_comun_no_se_comparan(monkeypatch):
    import clusterer
    llamadas = []
    original = clusterer.SequenceMatcher.ratio
    monkeypatch.setattr(clusterer.SequenceMatcher, "ratio", lambda self: llamadas.append(1) or original(self))
    agrupar([a("amor roma omar"), a("mora ramo arom")])  # mismas letras, ninguna palabra en común
    assert llamadas == []
