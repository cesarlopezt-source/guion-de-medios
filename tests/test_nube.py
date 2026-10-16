"""Modo nube del portal: login, 401 y búsqueda en vivo. El store usa SQLite temporal (misma interfaz)."""
import pytest

import ajustes
import store


class HiloFalso:
    lanzados = 0

    def __init__(self, target=None, daemon=None, **kw):
        self.target = target

    def start(self):
        HiloFalso.lanzados += 1


@pytest.fixture
def nube(monkeypatch, tmp_path):
    monkeypatch.setattr(ajustes, "DB_PATH", tmp_path / "n.db")
    monkeypatch.setattr(ajustes, "MODO", "nube")
    monkeypatch.setenv("APP_PASSWORD", "clave")
    import app as app_mod
    store.init_db()
    app_mod.app.config["TESTING"] = True
    app_mod.app.secret_key = "pruebas"
    app_mod._buscando.clear()
    HiloFalso.lanzados = 0
    monkeypatch.setattr(app_mod.threading, "Thread", HiloFalso)
    return app_mod


def entrar(cliente):
    return cliente.post("/login", data={"password": "clave"})


def test_sin_sesion_pagina_redirige_y_api_401(nube):
    c = nube.app.test_client()
    r = c.get("/")
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")
    r = c.get("/api/news?paises=SV&temas=Economía")
    assert r.status_code == 401 and r.get_json() == {"error": "Sesión expirada"}
    assert c.get("/static/app.js").status_code == 200


def test_login_correcto_e_incorrecto(nube):
    c = nube.app.test_client()
    r = c.post("/login", data={"password": "mala"})
    assert r.status_code == 200 and "Contraseña incorrecta" in r.get_data(as_text=True)
    assert c.get("/").status_code == 302
    assert entrar(c).status_code == 302
    assert c.get("/").status_code == 200


def test_login_sin_app_password_configurada_no_entra(nube, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD")
    c = nube.app.test_client()
    c.post("/login", data={"password": ""})
    assert c.get("/").status_code == 302


def test_logout(nube):
    c = nube.app.test_client()
    entrar(c)
    c.get("/logout")
    assert c.get("/").status_code == 302


def test_meta_con_datos_viejos_lanza_una_sola_busqueda(nube):
    c = nube.app.test_client()
    entrar(c)
    c.get("/api/meta")
    c.get("/api/meta")
    assert HiloFalso.lanzados == 1


def test_meta_con_datos_frescos_no_lanza(nube):
    corrida = store.iniciar_corrida(origen="pc")
    store.finalizar_corrida(corrida, 5, True)
    c = nube.app.test_client()
    entrar(c)
    m = c.get("/api/meta").get_json()
    assert HiloFalso.lanzados == 0 and m["en_curso"] is False


def test_meta_informa_origen_en_curso(nube):
    store.intentar_iniciar_corrida("nube")
    c = nube.app.test_client()
    entrar(c)
    m = c.get("/api/meta").get_json()
    assert m["en_curso"] is True and m["origen_en_curso"] == "nube"
    assert HiloFalso.lanzados == 0


def test_actualizar_en_nube_no_usa_subprocess(nube, monkeypatch):
    monkeypatch.setattr(nube.subprocess, "Popen", lambda *a, **k: pytest.fail("no debía usar subprocess"))
    c = nube.app.test_client()
    entrar(c)
    assert c.post("/api/actualizar").get_json() == {"iniciado": True}
    assert HiloFalso.lanzados == 1


def test_busqueda_en_vivo_llama_watcher_en_modo_nube(nube, monkeypatch):
    llamadas = []
    monkeypatch.setattr(nube.watcher, "correr", lambda **k: llamadas.append(k) or {"ok": True})
    nube._buscando.set()
    nube._buscar()
    assert llamadas == [{"origen": "nube", "verificar_enlaces": False}]
    assert not nube._buscando.is_set()
