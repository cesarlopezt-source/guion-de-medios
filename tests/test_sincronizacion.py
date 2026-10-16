from datetime import datetime, timezone

import psycopg
import pytest

from sincronizacion import FUENTE_SYNC, Sincronizacion
from store import postgres, sqlite

MESES = [(10, 2026)]


def art(url, mes=10, **kw):
    base = {"titulo": "T " + url, "resumen": "R", "url": url, "fuente": "LPG", "pais": "SV",
            "publicado": datetime(2026, mes, 5, 12, tzinfo=timezone.utc), "via": "rss",
            "temas": ["Economía"], "personajes": [], "menciona_sv": False}
    base.update(kw)
    return base


def noticia(titulo):
    return {"titulo": titulo, "resumen": "R", "pais": "SV", "temas": ["Economía"], "personajes": [],
            "menciona_sv": False, "fuentes": [{"nombre": "LPG", "url": "https://lpg/" + titulo}],
            "publicado": "2026-10-05T12:00:00+00:00", "n_fuentes": 1, "puntaje": 50.0, "estrellas": 3}


@pytest.fixture
def bases(tmp_path, pg_dsn):
    local = tmp_path / "pc.db"
    sqlite.init_db(local)
    postgres.init_db(pg_dsn)
    return local, pg_dsn


def corrida_completa(local, nube, meses=MESES):
    s = Sincronizacion(local, nube)
    assert s.antes() is True
    s.despues(meses)
    s.al_final(True)
    return s


def test_baja_articulos_de_la_nube_y_avanza_marca(bases):
    local, nube = bases
    postgres.guardar_articulos([art("vivo1")], nube, origen="nube")
    corrida_completa(local, nube)
    bajados = sqlite.articulos_desde(None, local, origen="nube")
    assert [a["url"] for a in bajados] == ["vivo1"]
    assert sqlite.obtener_marca("bajada_articulos", local) is not None


def test_no_baja_articulos_origen_pc(bases):
    local, nube = bases
    postgres.guardar_articulos([art("de-la-pc")], nube, origen="pc")
    corrida_completa(local, nube)
    assert sqlite.articulos_desde(None, local) == []


def test_sube_articulos_noticias_y_guiones(bases):
    local, nube = bases
    sqlite.guardar_articulos([art("local1")], local)
    sqlite.reemplazar_noticias(10, 2026, [noticia("N1")], local)
    sqlite.guardar_guion([{"titulo": "A"}], "texto", 1, 0.0, local)
    corrida_completa(local, nube)
    assert [a["url"] for a in postgres.articulos_desde(None, nube)] == ["local1"]
    assert [n["titulo"] for n in postgres.obtener_noticias(10, 2026, nube)] == ["N1"]
    assert postgres.uids_guiones(nube) == sqlite.uids_guiones(local)


def test_sube_estado_fuentes_y_enlaces(bases):
    local, nube = bases
    sqlite.registrar_estado_fuente({"nombre": "LPG", "pais": "SV", "tipo": "rss"}, True, 4, None, local)
    sqlite.guardar_estado_enlaces({"https://a/1": False}, local)
    corrida_completa(local, nube)
    assert "LPG" in {e["fuente"] for e in postgres.obtener_estado_fuentes(nube)}
    assert postgres.obtener_estado_enlaces(["https://a/1"], nube) == {"https://a/1": False}


def test_corrida_remota_queda_cerrada_con_origen_pc(bases):
    local, nube = bases
    corrida_completa(local, nube)
    assert postgres.corrida_en_curso(nube) is None
    assert postgres.ultima_corrida(nube)["origen"] == "pc"


def test_repetir_no_duplica(bases):
    local, nube = bases
    sqlite.guardar_articulos([art("local1")], local)
    postgres.guardar_articulos([art("vivo1")], nube, origen="nube")
    sqlite.guardar_guion([{"titulo": "A"}], "t", 1, 0.0, local)
    corrida_completa(local, nube)
    corrida_completa(local, nube)
    assert sorted(a["url"] for a in postgres.articulos_desde(None, nube)) == ["local1", "vivo1"]
    assert len(sqlite.articulos_desde(None, local)) == 2
    assert len(postgres.uids_guiones(nube)) == 1


def test_fallo_al_subir_no_avanza_marca(bases, monkeypatch):
    local, nube = bases
    sqlite.guardar_articulos([art("local1")], local)

    def caida(*a, **k):
        raise psycopg.OperationalError("se cortó la conexión")
    monkeypatch.setattr(postgres, "guardar_articulos", caida)
    s = Sincronizacion(local, nube)
    s.antes()
    s.despues(MESES)  # no debe lanzar
    s.al_final(True)
    assert sqlite.obtener_marca("subida_articulos", local) is None
    estado = {e["fuente"]: e for e in sqlite.obtener_estado_fuentes(local)}[FUENTE_SYNC["nombre"]]
    assert estado["ok"] is False and "se cortó" in estado["error"]
    monkeypatch.undo()
    corrida_completa(local, nube)  # la siguiente corrida sube lo pendiente
    assert [a["url"] for a in postgres.articulos_desde(None, nube)] == ["local1"]


def test_sin_conexion_antes_devuelve_true_y_desactiva(tmp_path):
    local = tmp_path / "pc.db"
    sqlite.init_db(local)
    s = Sincronizacion(local, "postgresql://nadie:x@127.0.0.1:1/nada?connect_timeout=2")
    assert s.antes() is True
    assert s.activa is False
    s.despues(MESES)
    s.al_final(True)
    estado = {e["fuente"]: e for e in sqlite.obtener_estado_fuentes(local)}[FUENTE_SYNC["nombre"]]
    assert estado["ok"] is False


def test_nube_ocupada_antes_devuelve_false(bases):
    local, nube = bases
    postgres.intentar_iniciar_corrida("nube", nube)
    assert Sincronizacion(local, nube).antes() is False


def test_poda_solo_meses_viejos(bases):
    local, nube = bases
    postgres.guardar_articulos([art("agosto", mes=8), art("septiembre", mes=9), art("octubre", mes=10)], nube)
    corrida_completa(local, nube, meses=[(10, 2026)])
    assert sorted(a["url"] for a in postgres.articulos_desde(None, nube)) == ["octubre", "septiembre"]


def test_guiones_de_la_nube_bajan_a_la_pc(bases):
    local, nube = bases
    postgres.guardar_guion([{"titulo": "Desde internet"}], "texto nube", 2, 0.0, nube)
    corrida_completa(local, nube)
    assert sqlite.listar_guiones(local)[0]["titulos"] == ["Desde internet"]


def test_estado_sincronizacion_registrado(bases):
    local, nube = bases
    corrida_completa(local, nube)
    estado = {e["fuente"]: e for e in sqlite.obtener_estado_fuentes(local)}[FUENTE_SYNC["nombre"]]
    assert estado["ok"] is True and estado["error"] is None


def test_primera_sincronizacion_sube_todos_los_meses(bases, monkeypatch):
    local, nube = bases
    sqlite.reemplazar_noticias(9, 2026, [noticia("Sep")], local)
    sqlite.reemplazar_noticias(10, 2026, [noticia("Oct")], local)
    corrida_completa(local, nube)
    assert [n["titulo"] for n in postgres.obtener_noticias(9, 2026, nube)] == ["Sep"]
    subidos = []
    original = postgres.reemplazar_noticias
    monkeypatch.setattr(postgres, "reemplazar_noticias", lambda m, a, n, d=None: subidos.append((m, a)) or original(m, a, n, d))
    corrida_completa(local, nube)
    assert subidos == [(10, 2026)]  # después, solo los meses reconstruidos
