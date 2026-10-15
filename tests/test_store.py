from datetime import datetime, timezone

import store


def a(url, mes=10, **kw):
    base = {"titulo": "T", "resumen": "R", "url": url, "fuente": "LPG", "pais": "SV",
            "publicado": datetime(2026, mes, 5, 12, tzinfo=timezone.utc), "via": "rss",
            "temas": ["Economía"], "personajes": [], "menciona_sv": False}
    base.update(kw)
    return base


def n(titulo="N", **kw):
    base = {"titulo": titulo, "resumen": "R", "pais": "SV", "temas": ["Economía"], "personajes": [],
            "menciona_sv": False, "fuentes": [{"nombre": "LPG", "url": "u"}],
            "publicado": "2026-10-05T12:00:00+00:00", "n_fuentes": 1, "puntaje": 50.0, "estrellas": 3}
    base.update(kw)
    return base


def test_dedup_por_url(db_path):
    store.init_db(db_path)
    assert store.guardar_articulos([a("u1")], db_path) == 1
    assert store.guardar_articulos([a("u1")], db_path) == 0


def test_articulos_por_mes(db_path):
    store.init_db(db_path)
    store.guardar_articulos([a("u1", mes=9), a("u2", mes=10)], db_path)
    res = store.obtener_articulos(10, 2026, db_path)
    assert len(res) == 1
    assert res[0]["publicado"].tzinfo is not None
    assert res[0]["temas"] == ["Economía"]
    assert res[0]["menciona_sv"] is False


def test_reemplazar_noticias_solo_ese_mes(db_path):
    store.init_db(db_path)
    store.reemplazar_noticias(9, 2026, [n("sep")], db_path)
    store.reemplazar_noticias(10, 2026, [n("oct1")], db_path)
    store.reemplazar_noticias(10, 2026, [n("oct2")], db_path)
    assert [x["titulo"] for x in store.obtener_noticias(9, 2026, db_path)] == ["sep"]
    oct_ = store.obtener_noticias(10, 2026, db_path)
    assert [x["titulo"] for x in oct_] == ["oct2"]
    assert oct_[0]["fuentes"] == [{"nombre": "LPG", "url": "u"}] and "id" in oct_[0]


def test_meses_disponibles_desc(db_path):
    store.init_db(db_path)
    store.reemplazar_noticias(9, 2026, [n()], db_path)
    store.reemplazar_noticias(1, 2027, [n()], db_path)
    assert store.meses_disponibles(db_path) == [(2027, 1), (2026, 9)]


def test_estado_fuente_upsert(db_path):
    store.init_db(db_path)
    f = {"nombre": "LPG", "pais": "SV", "tipo": "rss"}
    store.registrar_estado_fuente(f, True, 5, None, db_path)
    store.registrar_estado_fuente(f, False, 0, "boom", db_path)
    est = store.obtener_estado_fuentes(db_path)
    assert len(est) == 1 and est[0]["ok"] is False and est[0]["error"] == "boom"


def test_ultima_corrida_ignora_en_curso(db_path):
    store.init_db(db_path)
    assert store.ultima_corrida(db_path) is None
    c1 = store.iniciar_corrida(db_path)
    store.finalizar_corrida(c1, 7, True, db_path)
    store.iniciar_corrida(db_path)
    assert store.ultima_corrida(db_path)["n_articulos_nuevos"] == 7


def test_guion_roundtrip(db_path):
    store.init_db(db_path)
    gid = store.guardar_guion([n("A")], "texto", 120, 0.8, db_path)
    lista = store.listar_guiones(db_path)
    assert lista[0]["titulos"] == ["A"] and lista[0]["id"] == gid
    g = store.obtener_guion(gid, db_path)
    assert g["texto"] == "texto" and g["noticias"][0]["titulo"] == "A"
    assert store.obtener_guion(999, db_path) is None


def test_mes_se_define_en_hora_de_el_salvador(db_path):
    store.init_db(db_path)
    # 1 nov 03:00 UTC = 31 oct 21:00 en El Salvador (UTC-6)
    store.guardar_articulos([a("u1", publicado=datetime(2026, 11, 1, 3, tzinfo=timezone.utc))], db_path)
    assert len(store.obtener_articulos(10, 2026, db_path)) == 1
    assert store.obtener_articulos(11, 2026, db_path) == []


def test_estado_enlaces_cache(db_path):
    store.init_db(db_path)
    store.guardar_estado_enlaces({"https://a": True, "https://b": False, "https://c": None}, db_path)
    assert store.obtener_estado_enlaces(["https://a", "https://b", "https://c", "https://z"], db_path) == \
        {"https://a": True, "https://b": False}


def test_urls_por_verificar_excluye_mes_actual_google_y_recientes(db_path):
    store.init_db(db_path)
    fuentes = [{"nombre": "A", "url": "https://a/1"}, {"nombre": "G", "url": "https://news.google.com/rss/articles/x"}]
    store.reemplazar_noticias(9, 2026, [n("sep", fuentes=fuentes), n("sep2", fuentes=[{"nombre": "B", "url": "https://b/2"}])], db_path)
    store.reemplazar_noticias(10, 2026, [n("oct", fuentes=[{"nombre": "C", "url": "https://c/3"}])], db_path)
    assert sorted(store.urls_por_verificar((10, 2026), 50, db_path)) == ["https://a/1", "https://b/2"]
    store.guardar_estado_enlaces({"https://a/1": True}, db_path)
    assert store.urls_por_verificar((10, 2026), 50, db_path) == ["https://b/2"]
    assert len(store.urls_por_verificar((10, 2026), 1, db_path)) == 1
