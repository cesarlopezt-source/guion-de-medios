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


def test_consultas_google_news_una_por_medio_con_site():
    q = consultas_google_news()
    lpg = [c for c in q if c["nombre"] == "Google News · La Prensa Gráfica"]
    assert len(lpg) == 1 and "site%3Alaprensagrafica.com" in lpg[0]["url"]
    assert lpg[0]["medio"] == "La Prensa Gráfica" and lpg[0]["pais"] == "SV"
    assert all("ceid=" in c["url"] and c["tipo"] == "google_news" for c in q)


def test_consultas_google_news_incluye_medios_inactivos():
    nombres = {c["nombre"] for c in consultas_google_news()}
    assert "Google News · El Faro" in nombres


def test_consultas_personaje_solo_medios_conocidos():
    q = [c for c in consultas_google_news() if c["nombre"] == "Google News · Personaje · Nayib Bukele"]
    assert len(q) == 1 and "Nayib+Bukele" in q[0]["url"] and "site%3A" not in q[0]["url"]
    assert q[0]["solo_medios_conocidos"] is True


def test_google_news_solo_medios_conocidos_filtra_y_asigna_pais():
    f = {**F, "tipo": "google_news", "solo_medios_conocidos": True}
    a = google_news.parsear(leer("google_news.xml"), f)
    assert "EL PAÍS" not in {x["fuente"] for x in a}
    pl = [x for x in a if x["fuente"] == "Prensa Libre"]
    assert len(pl) == 1 and pl[0]["pais"] == "GT"


def test_google_news_usa_medio_configurado_y_descarta_titulo_vacio():
    f = {**F, "tipo": "google_news", "medio": "El Diario de Hoy"}
    a = google_news.parsear(leer("google_news.xml"), f)
    assert all(x["fuente"] == "El Diario de Hoy" for x in a)
    assert a[0]["titulo"] == "Remesas crecen 5%"
    assert len(a) == 4


def test_fuentes_paises_validos():
    assert {f["pais"] for f in FUENTES} == {"SV", "GT", "HN", "NI", "CR", "PA", "REG"}


def test_google_news_sin_medio_mapea_dominio_de_source():
    a = google_news.parsear(leer("google_news.xml"), {**F, "tipo": "google_news"})
    assert a[0]["fuente"] == "La Prensa Gráfica"
    assert a[1]["fuente"] == "Diario El Mundo"
    assert "Google News" not in {x["fuente"] for x in a}  # el titular igual al nombre del medio se descarta
    assert len(a) == 4
