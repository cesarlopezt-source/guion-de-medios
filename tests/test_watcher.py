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
