from datetime import datetime, timezone

import pytest

import ajustes
import store
from tests.fakes import N1, N2

AHORA = datetime.now(timezone.utc)


def noticia(titulo, pais, temas, personajes=(), puntaje=50.0):
    return {"titulo": titulo, "resumen": "r", "pais": pais, "temas": list(temas), "personajes": list(personajes),
            "menciona_sv": False, "fuentes": [{"nombre": "M", "url": "https://m/" + titulo}],
            "publicado": AHORA.isoformat(), "n_fuentes": 1, "puntaje": puntaje, "estrellas": 3}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(ajustes, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(ajustes, "LOCK_PATH", tmp_path / "w.lock")
    import app as app_mod
    store.init_db()
    store.reemplazar_noticias(AHORA.month, AHORA.year, [
        noticia("sv-eco", "SV", ["Economía"], puntaje=10),
        noticia("sv-eco-bukele", "SV", ["Economía", "Política"], ["Nayib Bukele"], puntaje=90),
        noticia("sv-dep", "SV", ["Deportes"]),
        noticia("gt-eco", "GT", ["Economía"]),
    ])
    app_mod.app.config["TESTING"] = True
    return app_mod.app.test_client()


def titulos(r):
    return [n["titulo"] for n in r.get_json()]


def test_index(client):
    assert client.get("/").status_code == 200


def test_news_filtra_por_pais_y_tema(client):
    assert set(titulos(client.get("/api/news?paises=SV&temas=Economía"))) == {"sv-eco", "sv-eco-bukele"}


def test_news_personajes_vacio_no_filtra(client):
    base = client.get("/api/news?paises=SV&temas=Economía").get_json()
    assert client.get("/api/news?paises=SV&temas=Economía&personajes=").get_json() == base


def test_news_personaje(client):
    assert titulos(client.get("/api/news?paises=SV,GT&temas=Economía&personajes=Nayib Bukele")) == ["sv-eco-bukele"]


def test_news_orden_importancia_por_defecto(client):
    assert titulos(client.get("/api/news?paises=SV&temas=Economía")) == ["sv-eco-bukele", "sv-eco"]


def test_news_sin_paises_vacio(client):
    assert client.get("/api/news?paises=&temas=Economía").get_json() == []


def test_news_mes_invalido_400(client):
    assert client.get("/api/news?paises=SV&temas=Economía&mes=13").status_code == 400


def test_meta_listas(client):
    m = client.get("/api/meta").get_json()
    assert [p["codigo"] for p in m["paises"]] == ["SV", "GT", "HN", "NI", "CR", "PA", "REG"]
    assert m["temas"][0] == "Economía" and m["temas"][-1] == "Otras"
    assert "Nayib Bukele" in m["personajes"]
    assert m["meses"] == [[AHORA.year, AHORA.month]] and m["en_curso"] is False
    assert m["ultima_actualizacion"] is None


def test_actualizar_en_curso(client, monkeypatch):
    import app as app_mod
    monkeypatch.setattr(app_mod.watcher, "esta_bloqueado", lambda *a, **k: True)
    assert client.post("/api/actualizar").get_json() == {"iniciado": False, "motivo": "en_curso"}


def test_actualizar_lanza_proceso(client, monkeypatch):
    import app as app_mod
    lanzados = []
    monkeypatch.setattr(app_mod.watcher, "esta_bloqueado", lambda *a, **k: False)
    monkeypatch.setattr(app_mod.subprocess, "Popen", lambda *a, **k: lanzados.append(a))
    assert client.post("/api/actualizar").get_json() == {"iniciado": True}
    assert lanzados and str(lanzados[0][0][-1]).endswith("watcher.py")


def test_fuentes_pagina(client):
    store.registrar_estado_fuente({"nombre": "Medio Z", "pais": "SV", "tipo": "rss"}, True, 4, None)
    r = client.get("/fuentes")
    assert r.status_code == 200 and "Medio Z" in r.get_data(as_text=True)


def test_guion_sin_noticias_400(client):
    r = client.post("/api/guion", json={"noticias": []})
    assert r.status_code == 400 and "error" in r.get_json()


def test_guion_sin_clave_503(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.post("/api/guion", json={"noticias": [N1]}).status_code == 503


def test_guion_guarda_historial(client, monkeypatch):
    import app as app_mod
    monkeypatch.setattr(app_mod.guionista, "generar_guion",
                        lambda ns, **k: {"texto": "[APERTURA]\nHola", "palabras": 1, "minutos": 0.0})
    r = client.post("/api/guion", json={"noticias": [N1, N2]}).get_json()
    assert r["texto"] == "[APERTURA]\nHola" and "id" in r
    assert client.get("/api/guiones").get_json()[0]["titulos"] == [N1["titulo"], N2["titulo"]]
    assert client.get(f"/api/guiones/{r['id']}").get_json()["texto"] == "[APERTURA]\nHola"
    assert client.get("/api/guiones/999").status_code == 404


def test_guion_export(client):
    r = client.post("/api/guion/export", json={"texto": "[APERTURA]\nHola", "formato": "word"})
    assert r.status_code == 200 and "guion_de_medios.docx" in r.headers["Content-Disposition"]
    r = client.post("/api/guion/export", json={"texto": "[APERTURA]\nHola", "formato": "pdf"})
    assert r.data[:4] == b"%PDF"


def test_export_noticias(client):
    r = client.post("/api/export", json={"items": [N1], "format": "excel"})
    assert r.status_code == 200 and "noticias_centroamerica.xlsx" in r.headers["Content-Disposition"]


def test_valorar_sin_clave_503(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.post("/api/valorar", json={"items": [N1]}).status_code == 503
