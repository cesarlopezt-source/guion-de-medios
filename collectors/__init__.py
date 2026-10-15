from urllib.parse import urlparse

import requests

from collectors import google_news, rss, web

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "es-419,es;q=0.9",
}
TIMEOUT = 15

_PARSERS = {"rss": rss.parsear, "google_news": google_news.parsear, "web": web.parsear}


def descargar(url: str) -> bytes:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.content


def recolectar(fuente: dict) -> tuple:
    """Devuelve (articulos, error). Nunca lanza: una fuente caída no detiene a las demás."""
    try:
        contenido = descargar(fuente["url"])
        articulos = _PARSERS[fuente["tipo"]](contenido, fuente)
        # Solo enlaces web: un feed hostil podría colar javascript: o data: en la pantalla.
        return [a for a in articulos if urlparse(a["url"]).scheme in ("http", "https")], None
    except Exception as exc:
        return [], str(exc)[:200]
