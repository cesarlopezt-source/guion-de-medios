import os
import time
from datetime import datetime, timezone

import pytest

import store
import watcher

AHORA = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
F1 = {"nombre": "Medio A", "pais": "SV", "tipo": "rss", "url": "a", "activa": True}
F2 = {"nombre": "Google News · Medio A", "pais": "SV", "tipo": "google_news", "url": "b", "activa": True}


def art(url, titulo="Remesas crecen en septiembre", via="rss"):
    return {"titulo": titulo, "resumen": "", "url": url, "fuente": "Medio A", "pais": "SV",
            "publicado": AHORA, "via": via}


@pytest.fixture
def rutas(tmp_path):
    return {"db_path": tmp_path / "t.db", "lock_path": tmp_path / "w.lock"}


def test_correr_guarda_y_construye(monkeypatch, rutas):
    resultados = {"a": ([art("u1")], None), "b": ([art("u2", "Otra noticia de economía", "google_news")], None)}
    monkeypatch.setattr(watcher, "recolectar", lambda f: resultados[f["url"]])
    r = watcher.correr([F1, F2], ahora=AHORA, **rutas)
    assert r == {"ok": True, "nuevos": 2, "fuentes_ok": 2, "fuentes_error": 0}
    assert len(store.obtener_noticias(10, 2026, rutas["db_path"])) == 2
    assert store.ultima_corrida(rutas["db_path"]) is not None


def test_fuente_que_falla_no_detiene(monkeypatch, rutas):
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([], "boom") if f["url"] == "a" else ([art("u2")], None))
    r = watcher.correr([F1, F2], ahora=AHORA, **rutas)
    assert r["fuentes_error"] == 1 and r["nuevos"] == 1
    estado = {e["fuente"]: e for e in store.obtener_estado_fuentes(rutas["db_path"])}
    assert estado["Medio A"]["ok"] is False and estado["Medio A"]["error"] == "boom"


def test_fuente_sin_articulos_cuenta_como_error_sin_mensaje(monkeypatch, rutas):
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([], None))
    r = watcher.correr([F1], ahora=AHORA, **rutas)
    assert r["fuentes_error"] == 1


def test_prioridad_rss_sobre_google_news(monkeypatch, rutas):
    monkeypatch.setattr(watcher, "recolectar",
                        lambda f: ([art("u1", via="google_news")], None) if f["url"] == "b" else ([art("u1")], None))
    watcher.correr([F2, F1], ahora=AHORA, **rutas)
    assert store.obtener_articulos(10, 2026, rutas["db_path"])[0]["via"] == "rss"


def test_clasifica_antes_de_guardar(monkeypatch, rutas):
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art("u1", "Bukele presenta presupuesto")], None))
    watcher.correr([F1], ahora=AHORA, **rutas)
    a = store.obtener_articulos(10, 2026, rutas["db_path"])[0]
    assert a["personajes"] == ["Nayib Bukele"] and "Economía" in a["temas"]


def test_bloqueo_activo_cancela(monkeypatch, rutas):
    rutas["lock_path"].write_text("123")
    monkeypatch.setattr(watcher, "recolectar", lambda f: pytest.fail("no debía recolectar"))
    assert watcher.correr([F1], ahora=AHORA, **rutas) == {"ok": False, "motivo": "en_curso"}
    assert watcher.esta_bloqueado(rutas["lock_path"]) is True


def test_bloqueo_viejo_se_reemplaza(monkeypatch, rutas):
    rutas["lock_path"].write_text("123")
    viejo = time.time() - 2 * 3600
    os.utime(rutas["lock_path"], (viejo, viejo))
    assert watcher.esta_bloqueado(rutas["lock_path"]) is False
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art("u1")], None))
    assert watcher.correr([F1], ahora=AHORA, **rutas)["ok"] is True


def test_libera_bloqueo_si_falla(monkeypatch, rutas):
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art("u1")], None))
    def explota(a):
        raise RuntimeError("x")
    monkeypatch.setattr(watcher, "clasificar", explota)
    with pytest.raises(RuntimeError):
        watcher.correr([F1], ahora=AHORA, **rutas)
    assert not rutas["lock_path"].exists()


def test_fuentes_por_defecto_activas_mas_google_news(monkeypatch):
    fs = watcher.fuentes_por_defecto()
    assert all(f["activa"] for f in fs)
    assert any(f["tipo"] == "google_news" for f in fs) and any(f["tipo"] == "rss" for f in fs)


def test_log_sin_consola_no_agrega_stream(monkeypatch, tmp_path):
    import logging
    import sys
    import ajustes
    monkeypatch.setattr(ajustes, "LOG_DIR", tmp_path)
    monkeypatch.setattr(sys, "stderr", None)
    raiz = logging.getLogger()
    antes = list(raiz.handlers)
    try:
        watcher._configurar_log()
        nuevos = [h for h in raiz.handlers if h not in antes]
        assert nuevos and all(type(h).__name__ == "RotatingFileHandler" for h in nuevos)
    finally:
        for h in raiz.handlers[:]:
            if h not in antes:
                raiz.removeHandler(h)
                h.close()


def test_mes_actual_en_hora_de_el_salvador(monkeypatch, rutas):
    # 1 nov 03:00 UTC = 31 oct en El Salvador: se reconstruye octubre
    ahora = datetime(2026, 11, 1, 3, tzinfo=timezone.utc)
    articulo = {**art("u1"), "publicado": ahora}
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([articulo], None))
    watcher.correr([F1], ahora=ahora, **rutas)
    assert len(store.obtener_noticias(10, 2026, rutas["db_path"])) == 1


def test_primeros_dias_del_mes_reconstruye_tambien_el_anterior(monkeypatch, rutas):
    # Una nota del 31 oct (hora SV) recolectada el 1 nov a mediodía debe aparecer en octubre.
    ahora = datetime(2026, 11, 1, 18, tzinfo=timezone.utc)
    tarde = {**art("u1"), "publicado": datetime(2026, 11, 1, 4, tzinfo=timezone.utc)}  # 31 oct 22:00 SV
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([tarde], None))
    watcher.correr([F1], ahora=ahora, **rutas)
    assert len(store.obtener_noticias(10, 2026, rutas["db_path"])) == 1


def test_reclasifica_articulos_guardados_al_reconstruir(monkeypatch, rutas):
    store.init_db(rutas["db_path"])
    viejo = {**art("u1", "Aguirre presenta propuesta"), "temas": ["Otras"], "personajes": [], "menciona_sv": False}
    store.guardar_articulos([viejo], rutas["db_path"])
    import config.personajes
    import classifier
    monkeypatch.setitem(config.personajes.PERSONAJES, "Aguirre", ["aguirre"])
    monkeypatch.setattr(classifier, "_PERSONAJES", {**classifier._PERSONAJES, "Aguirre": classifier._patron(["aguirre"])})
    import noticias
    monkeypatch.setattr(noticias, "_ORDEN_PERSONAJES", list(noticias._ORDEN_PERSONAJES) + ["Aguirre"])
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([], None))
    watcher.correr([F1], ahora=AHORA, **rutas)
    assert store.obtener_noticias(10, 2026, rutas["db_path"])[0]["personajes"] == ["Aguirre"]


def test_verifica_enlaces_de_meses_anteriores(monkeypatch, rutas):
    import link_checker
    store.init_db(rutas["db_path"])
    viejo = {"titulo": "v", "resumen": "", "pais": "SV", "temas": ["Economía"], "personajes": [], "menciona_sv": False,
             "fuentes": [{"nombre": "A", "url": "https://a/viejo"}], "publicado": "2026-09-01T00:00:00+00:00",
             "n_fuentes": 1, "puntaje": 1.0, "estrellas": 1}
    store.reemplazar_noticias(9, 2026, [viejo], rutas["db_path"])
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([], None))
    monkeypatch.setattr(link_checker, "check_urls", lambda urls: {u: False for u in urls})
    watcher.correr([F1], ahora=AHORA, **rutas)
    assert store.obtener_estado_enlaces(["https://a/viejo"], rutas["db_path"]) == {"https://a/viejo": False}


# ---- Bloqueo por base, origen y sincronización ----

class SyncFalso:
    def __init__(self, antes=True):
        self._antes = antes
        self.llamadas = []

    def antes(self):
        self.llamadas.append("antes")
        return self._antes

    def despues(self, meses):
        self.llamadas.append(("despues", meses))

    def al_final(self, ok):
        self.llamadas.append(("al_final", ok))


def test_nube_usa_bloqueo_por_base(monkeypatch, rutas):
    store.init_db(rutas["db_path"])
    store.intentar_iniciar_corrida("pc", rutas["db_path"])
    monkeypatch.setattr(watcher, "recolectar", lambda f: pytest.fail("no debía recolectar"))
    r = watcher.correr([F1], ahora=AHORA, origen="nube", verificar_enlaces=False, **rutas)
    assert r == {"ok": False, "motivo": "en_curso"}
    assert not rutas["lock_path"].exists()


def test_nube_guarda_origen_nube(monkeypatch, rutas):
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art("u1")], None))
    assert watcher.correr([F1], ahora=AHORA, origen="nube", verificar_enlaces=False, **rutas)["ok"] is True
    assert store.articulos_desde(None, rutas["db_path"])[0]["origen"] == "nube"
    assert store.ultima_corrida(rutas["db_path"])["origen"] == "nube"


def test_sin_verificar_enlaces_no_llama_link_checker(monkeypatch, rutas):
    import link_checker
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art("u1")], None))
    monkeypatch.setattr(link_checker, "check_urls", lambda urls: pytest.fail("no debía verificar"))
    assert watcher.correr([F1], ahora=AHORA, verificar_enlaces=False, **rutas)["ok"] is True


def test_corrida_fallida_se_cierra(monkeypatch, rutas):
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art("u1")], None))
    monkeypatch.setattr(watcher, "clasificar", lambda a: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        watcher.correr([F1], ahora=AHORA, **rutas)
    assert store.corrida_en_curso(rutas["db_path"]) is None
    assert store.ultima_corrida(rutas["db_path"]) is None  # cerrada con ok = False


def test_sincronizar_antes_false_cancela(monkeypatch, rutas):
    sync = SyncFalso(antes=False)
    monkeypatch.setattr(watcher, "recolectar", lambda f: pytest.fail("no debía recolectar"))
    assert watcher.correr([F1], ahora=AHORA, sincronizar=sync, **rutas) == {"ok": False, "motivo": "en_curso"}
    assert sync.llamadas == ["antes"]
    assert store.corrida_en_curso(rutas["db_path"]) is None


def test_sincronizar_recibe_meses_reconstruidos(monkeypatch, rutas):
    sync = SyncFalso()
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art("u1")], None))
    watcher.correr([F1], ahora=AHORA, sincronizar=sync, **rutas)
    assert sync.llamadas == ["antes", ("despues", watcher.meses_a_reconstruir(AHORA)), ("al_final", True)]


def test_sincronizar_al_final_false_si_falla(monkeypatch, rutas):
    sync = SyncFalso()
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art("u1")], None))
    monkeypatch.setattr(watcher, "clasificar", lambda a: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        watcher.correr([F1], ahora=AHORA, sincronizar=sync, **rutas)
    assert sync.llamadas[-1] == ("al_final", False)


def test_sincronizacion_por_defecto_solo_con_database_url(monkeypatch):
    import ajustes
    monkeypatch.setattr(ajustes, "MODO", "pc")
    monkeypatch.setattr(ajustes, "DATABASE_URL", None)
    assert watcher._sincronizacion_por_defecto() is None
    monkeypatch.setattr(ajustes, "DATABASE_URL", "postgresql://x")
    assert type(watcher._sincronizacion_por_defecto()).__name__ == "Sincronizacion"
    monkeypatch.setattr(ajustes, "MODO", "nube")
    assert watcher._sincronizacion_por_defecto() is None


def test_enlace_real_de_google_news(monkeypatch, rutas):
    from collectors import google_enlaces
    g1, g2 = "https://news.google.com/rss/articles/g1", "https://news.google.com/rss/articles/g2"
    monkeypatch.setattr(google_enlaces, "enlace_real", lambda u, sesion=None: {g1: "https://medio.com/1"}.get(u, ""))
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art(g1, via="google_news"),
                                                            art(g2, "Otra noticia de economía", "google_news")], None))
    watcher.correr([F2], ahora=AHORA, **rutas)
    urls = {f["url"] for n in store.obtener_noticias(10, 2026, rutas["db_path"]) for f in n["fuentes"]}
    assert urls == {"https://medio.com/1", g2}  # sin enlace real se queda el de Google
    assert store.urls_sin_enlace(10, rutas["db_path"]) == []  # el fallido quedó marcado: no se reintenta


def test_enlaces_atrasados_se_completan(monkeypatch, rutas):
    from collectors import google_enlaces
    g1 = "https://news.google.com/rss/articles/g1"
    store.init_db(rutas["db_path"])
    store.guardar_articulos([{**art(g1, via="google_news"), "temas": [], "personajes": []}], rutas["db_path"])
    assert store.urls_sin_enlace(10, rutas["db_path"]) == [g1]
    monkeypatch.setattr(google_enlaces, "enlace_real", lambda u, sesion=None: "https://medio.com/1")
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art("u1")], None))
    watcher.correr([F1], ahora=AHORA, **rutas)
    urls = {f["url"] for n in store.obtener_noticias(10, 2026, rutas["db_path"]) for f in n["fuentes"]}
    assert "https://medio.com/1" in urls


def test_enlace_fallido_por_ahora_se_reintenta(monkeypatch, rutas):
    from collectors import google_enlaces
    g1 = "https://news.google.com/rss/articles/g1"
    monkeypatch.setattr(google_enlaces, "enlace_real", lambda u, sesion=None: None)  # p. ej. Google en pausa
    monkeypatch.setattr(watcher, "recolectar", lambda f: ([art(g1, via="google_news")], None))
    watcher.correr([F2], ahora=AHORA, **rutas)
    assert store.urls_sin_enlace(10, rutas["db_path"]) == [g1]


def test_nube_no_busca_enlaces_reales(monkeypatch, rutas):
    from collectors import google_enlaces
    llamadas = []
    monkeypatch.setattr(google_enlaces, "enlace_real", lambda u, sesion=None: llamadas.append(u) or "https://m/1")
    monkeypatch.setattr(watcher, "recolectar",
                        lambda f: ([art("https://news.google.com/rss/articles/g1", via="google_news")], None))
    watcher.correr([F2], ahora=AHORA, origen="nube", verificar_enlaces=False, **rutas)
    assert llamadas == []
