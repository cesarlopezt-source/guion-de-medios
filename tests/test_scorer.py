from datetime import datetime, timedelta, timezone

from scorer import estrellas, factor_recencia, puntuar


def hace(horas):
    return datetime.now(timezone.utc) - timedelta(hours=horas)


def test_factor_recencia_tramos():
    assert factor_recencia(hace(1)) == 1.0
    assert factor_recencia(hace(3)) == 0.75
    assert factor_recencia(hace(8)) == 0.5
    assert factor_recencia(hace(20)) == 0.25
    assert factor_recencia(hace(48)) == 0.1


def test_factor_recencia_sin_zona_es_utc():
    assert factor_recencia(hace(1).replace(tzinfo=None)) == 1.0


def test_puntuar_cuenta_fuentes_distintas():
    c = [{"fuente": "A", "publicado": hace(1)}, {"fuente": "A", "publicado": hace(1)}, {"fuente": "B", "publicado": hace(5)}]
    assert puntuar(c) == 2 * 40 + 1.0 * 60


def test_estrellas():
    assert estrellas(100, 100) == 5
    assert estrellas(10, 100) == 1
    assert estrellas(50, 0) == 1
