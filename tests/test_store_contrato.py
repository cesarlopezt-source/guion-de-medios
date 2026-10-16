"""Contrato común de los motores de store: corre con SQLite y con Postgres."""
import sqlite3
from datetime import datetime, timezone

import pytest


def art(url, mes=10, dia=5, **kw):
    base = {"titulo": "T " + url, "resumen": "R", "url": url, "fuente": "LPG", "pais": "SV",
            "publicado": datetime(2026, mes, dia, 12, tzinfo=timezone.utc), "via": "rss",
            "temas": ["Economía"], "personajes": [], "menciona_sv": False}
    base.update(kw)
    return base


@pytest.fixture
def m(motor):
    modulo, destino = motor
    modulo.init_db(destino)
    return modulo, destino


def test_origen_por_defecto_y_explicito(m):
    s, d = m
    s.guardar_articulos([art("u1")], d)
    s.guardar_articulos([art("u2")], d, origen="nube")
    nube = s.articulos_desde(None, d, origen="nube")
    assert [a["url"] for a in nube] == ["u2"] and nube[0]["origen"] == "nube"
    assert {a["url"]: a["origen"] for a in s.articulos_desde(None, d)} == {"u1": "pc", "u2": "nube"}


def test_articulos_desde_marca(m):
    s, d = m
    s.guardar_articulos([art("u1")], d)
    marca = s.articulos_desde(None, d)[-1]["recolectado"]
    s.guardar_articulos([art("u2")], d)
    assert [a["url"] for a in s.articulos_desde(marca, d)] == ["u2"]


def test_guardar_respeta_recolectado_y_origen_del_articulo(m):
    s, d = m
    s.guardar_articulos([art("u1", recolectado="2026-10-01T00:00:00+00:00", origen="nube")], d)
    a = s.articulos_desde(None, d)[0]
    assert a["origen"] == "nube"
    assert datetime.fromisoformat(a["recolectado"]) == datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_articulos_desde_devuelve_campos_completos(m):
    s, d = m
    s.guardar_articulos([art("u1", temas=["Economía", "Mujeres"], personajes=["Nayib Bukele"])], d)
    a = s.articulos_desde(None, d)[0]
    assert a["temas"] == ["Economía", "Mujeres"] and a["personajes"] == ["Nayib Bukele"]
    assert a["publicado"] == datetime(2026, 10, 5, 12, tzinfo=timezone.utc)


def test_intentar_iniciar_corrida_bloquea(m):
    s, d = m
    c1 = s.intentar_iniciar_corrida("pc", d)
    assert isinstance(c1, int)
    assert s.intentar_iniciar_corrida("nube", d) is None
    s.finalizar_corrida(c1, 0, True, d)
    assert isinstance(s.intentar_iniciar_corrida("nube", d), int)


def test_corrida_abandonada_expira(m):
    s, d = m
    assert s.intentar_iniciar_corrida("pc", d) is not None
    assert s.intentar_iniciar_corrida("nube", d, bloqueo_min=0) is not None


def test_corrida_en_curso(m):
    s, d = m
    assert s.corrida_en_curso(d) is None
    c = s.intentar_iniciar_corrida("nube", d)
    assert s.corrida_en_curso(d)["origen"] == "nube"
    s.finalizar_corrida(c, 3, True, d)
    assert s.corrida_en_curso(d) is None
    assert s.ultima_corrida(d)["origen"] == "nube"


def test_guiones_uid_roundtrip(m, tmp_path):
    s, d = m
    gid = s.guardar_guion([{"titulo": "A"}], "texto", 10, 0.1, d)
    uids = s.uids_guiones(d)
    assert len(uids) == 1
    g = s.guiones_por_uid(uids, d)[0]
    assert g["texto"] == "texto" and g["noticias"] == [{"titulo": "A"}] and g["uid"] in uids
    assert s.obtener_guion(gid, d)["uid"] == g["uid"]
    otro = tmp_path / "otro.db"
    from store import sqlite
    sqlite.init_db(otro)
    assert sqlite.insertar_guiones([g], otro) == 1
    assert sqlite.insertar_guiones([g], otro) == 0
    assert sqlite.uids_guiones(otro) == uids


def test_insertar_guiones_en_el_motor(m):
    s, d = m
    g = {"uid": "abc", "creado": "2026-10-01T00:00:00+00:00", "noticias": [{"titulo": "Z"}], "texto": "t",
         "palabras": 1, "minutos": 0.0}
    assert s.insertar_guiones([g], d) == 1
    assert s.insertar_guiones([g], d) == 0
    assert s.listar_guiones(d)[0]["titulos"] == ["Z"]


def test_enlaces_desde_y_verificado_explicito(m):
    s, d = m
    s.guardar_estado_enlaces({"u": True}, d, verificado="2026-10-01T00:00:00+00:00")
    estado = s.enlaces_desde(None, d)
    assert estado["u"][0] is True
    assert datetime.fromisoformat(estado["u"][1]) == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert s.enlaces_desde("2026-10-02T00:00:00+00:00", d) == {}


def test_podar_articulos(m):
    s, d = m
    s.guardar_articulos([art("ago", mes=8), art("oct", mes=10)], d)
    assert s.podar_articulos("2026-09-01T06:00:00+00:00", d) == 1
    assert [a["url"] for a in s.articulos_desde(None, d)] == ["oct"]


def test_mes_en_hora_sv(m):
    s, d = m
    s.guardar_articulos([art("u1", publicado=datetime(2026, 11, 1, 3, tzinfo=timezone.utc))], d)
    assert len(s.obtener_articulos(10, 2026, d)) == 1
    assert s.obtener_articulos(11, 2026, d) == []


def test_noticias_y_meses(m):
    s, d = m
    n = {"titulo": "N", "resumen": "R", "pais": "SV", "temas": ["Economía"], "personajes": [], "menciona_sv": False,
         "fuentes": [{"nombre": "LPG", "url": "https://lpg/1"}], "publicado": "2026-10-05T12:00:00+00:00",
         "n_fuentes": 1, "puntaje": 50.0, "estrellas": 3}
    s.reemplazar_noticias(10, 2026, [n], d)
    s.reemplazar_noticias(10, 2026, [{**n, "titulo": "N2"}], d)
    assert [x["titulo"] for x in s.obtener_noticias(10, 2026, d)] == ["N2"]
    assert s.meses_disponibles(d) == [(2026, 10)]
    assert s.urls_por_verificar((11, 2026), 10, d) == ["https://lpg/1"]


def test_estado_fuentes(m):
    s, d = m
    f = {"nombre": "LPG", "pais": "SV", "tipo": "rss"}
    s.registrar_estado_fuente(f, True, 5, None, d)
    s.registrar_estado_fuente(f, False, 0, "boom", d)
    est = s.obtener_estado_fuentes(d)
    assert len(est) == 1 and est[0]["ok"] is False and est[0]["error"] == "boom"


# ---- Solo SQLite ----

def test_migracion_agrega_origen_y_uid_sin_perder_datos(tmp_path):
    from store import sqlite
    ruta = tmp_path / "vieja.db"
    conn = sqlite3.connect(ruta)
    conn.executescript("""
        CREATE TABLE articulos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, resumen TEXT,
            url TEXT UNIQUE NOT NULL, fuente TEXT NOT NULL, pais TEXT NOT NULL, temas TEXT NOT NULL,
            personajes TEXT NOT NULL, menciona_sv INTEGER NOT NULL DEFAULT 0, publicado TEXT NOT NULL,
            recolectado TEXT NOT NULL, via TEXT NOT NULL);
        INSERT INTO articulos (titulo, url, fuente, pais, temas, personajes, publicado, recolectado, via)
            VALUES ('viejo', 'u-vieja', 'LPG', 'SV', '[]', '[]', '2026-10-05T12:00:00+00:00', '2026-10-05T12:00:00+00:00', 'rss');
        CREATE TABLE corridas (id INTEGER PRIMARY KEY AUTOINCREMENT, inicio TEXT NOT NULL, fin TEXT,
            n_articulos_nuevos INTEGER, ok INTEGER);
        CREATE TABLE guiones (id INTEGER PRIMARY KEY AUTOINCREMENT, creado TEXT NOT NULL, noticias TEXT NOT NULL,
            texto TEXT NOT NULL, palabras INTEGER NOT NULL, minutos_estimados REAL NOT NULL);
        INSERT INTO guiones (creado, noticias, texto, palabras, minutos_estimados)
            VALUES ('2026-10-05T12:00:00+00:00', '[{"titulo": "A"}]', 'texto viejo', 2, 0.0);
    """)
    conn.commit()
    conn.close()
    sqlite.init_db(ruta)
    assert sqlite.articulos_desde(None, ruta)[0]["origen"] == "pc"
    uids = sqlite.uids_guiones(ruta)
    assert len(uids) == 1 and all(uids)
    assert sqlite.listar_guiones(ruta)[0]["titulos"] == ["A"]
    sqlite.init_db(ruta)  # idempotente
    assert sqlite.uids_guiones(ruta) == uids


def test_marcas(tmp_path):
    from store import sqlite
    ruta = tmp_path / "m.db"
    sqlite.init_db(ruta)
    assert sqlite.obtener_marca("x", ruta) is None
    sqlite.guardar_marca("x", "2026-10-01", ruta)
    sqlite.guardar_marca("x", "2026-10-02", ruta)
    assert sqlite.obtener_marca("x", ruta) == "2026-10-02"
