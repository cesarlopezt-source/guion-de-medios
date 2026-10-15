from datetime import datetime, timezone
from pathlib import Path

import collectors
from collectors import web

FIX = Path(__file__).parent / "fixtures"
F = {"nombre": "Medio Web", "pais": "SV", "tipo": "web", "url": "https://medio.sv/", "activa": True,
     "selectores": {"item": "article.nota", "titulo": "h2", "enlace": "h2 a", "resumen": "p.bajada",
                    "fecha": "time"}}


def contenido():
    return (FIX / "portada.html").read_bytes()


def test_web_extrae_validos():
    a = web.parsear(contenido(), F)
    assert len(a) == 2 and all(x["via"] == "web" for x in a)
    assert a[0]["titulo"] == "Exportaciones suben 8%"
    assert a[0]["resumen"] == "Las ventas al exterior crecieron."


def test_web_enlace_relativo_absoluto():
    assert web.parsear(contenido(), F)[1]["url"] == "https://medio.sv/economia/nota-2"


def test_web_fecha_con_zona_a_utc():
    assert web.parsear(contenido(), F)[0]["publicado"] == datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc)


def test_recolectar_despacha_web(monkeypatch):
    monkeypatch.setattr(collectors, "descargar", lambda url: contenido())
    articulos, error = collectors.recolectar(F)
    assert error is None and len(articulos) == 2
