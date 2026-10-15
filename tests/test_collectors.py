from datetime import datetime, timezone
from pathlib import Path

import requests

import collectors
from collectors import google_news, rss
from config.fuentes import FUENTES, consultas_google_news

FIX = Path(__file__).parent / "fixtures"
F = {"nombre": "Medio X", "pais": "SV", "tipo": "rss", "url": "u", "activa": True}


def leer(nombre):
    return (FIX / nombre).read_bytes()


def test_rss_campos_y_limpieza():
    a = rss.parsear(leer("rss_simple.xml"), F)
    assert len(a) == 3 and a[0]["fuente"] == "Medio X" and a[0]["via"] == "rss"
    assert a[0]["resumen"] == "Texto"
    assert a[0]["url"] == "https://medio.sv/remesas" and a[0]["pais"] == "SV"


def test_rss_fecha_con_zona_a_utc():
    a = rss.parsear(leer("rss_simple.xml"), F)
    assert a[0]["publicado"] == datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc)


def test_rss_fechas_ausente_y_futura_son_ahora():
    a = rss.parsear(leer("rss_simple.xml"), F)
    ahora = datetime.now(timezone.utc)
    assert all(x["publicado"] <= ahora and x["publicado"].tzinfo for x in a)
    assert (ahora - a[2]["publicado"]).total_seconds() < 60


def test_google_news_quita_sufijo_y_usa_source():
    a = google_news.parsear(leer("google_news.xml"), {**F, "tipo": "google_news"})
    assert a[0]["titulo"] == "Remesas crecen 5%" and a[0]["fuente"] == "La Prensa Gráfica"
    assert a[0]["via"] == "google_news"
    assert a[1]["titulo"] == "Inversión en zona franca"


def test_recolectar_fuente_caida(monkeypatch):
    def falla(url):
        raise requests.Timeout("t")
    monkeypatch.setattr(collectors, "descargar", falla)
    assert collectors.recolectar(F) == ([], "t")


def test_recolectar_ok(monkeypatch):
    monkeypatch.setattr(collectors, "descargar", lambda url: leer("rss_simple.xml"))
    articulos, error = collectors.recolectar(F)
    assert error is None and len(articulos) == 3


def test_consultas_google_news():
    q = consultas_google_news()
    assert any(c["nombre"] == "Google News · SV · Economía" for c in q)
    assert all("ceid=" in c["url"] and c["tipo"] == "google_news" for c in q)
    assert any("Nayib+Bukele" in c["url"] or "Nayib%20Bukele" in c["url"] for c in q)


def test_fuentes_paises_validos():
    assert {f["pais"] for f in FUENTES} == {"SV", "GT", "HN", "NI", "CR", "PA", "REG"}
