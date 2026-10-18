"""Convierte los enlaces de Google News (news.google.com/rss/articles/...) en el enlace real del medio.

El enlace de Google no abre fuera del navegador (da 405 desde un PDF), así que se guarda también el real.
Google ya no lo trae en el propio enlace: hay que leer la firma de la página del artículo y pedirlo a su API.
Google corta con 429 si se le pide muy rápido: se espacian los pedidos y, ante un 429, se pausa un rato.
"""
import json
import re
import threading
import time
from urllib.parse import quote, urlparse

import requests

TIMEOUT = 15
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
}
_API = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
_FIRMA = re.compile(r'data-n-a-sg="([^"]+)"')
_FECHA = re.compile(r'data-n-a-ts="([^"]+)"')

INTERVALO_S = 3.0        # mínimo entre dos pedidos a Google
PAUSA_429_S = 3 * 3600   # tras un bloqueo (429 o página "sorry") no se le pide nada a Google por este tiempo
_candado = threading.Lock()
_ultimo = 0.0
_pausa_hasta = 0.0


class _Limitado(Exception):
    """Google respondió 429 (demasiados pedidos)."""


def es_de_google(url: str) -> bool:
    p = urlparse(url or "")
    return p.netloc == "news.google.com" and "/articles/" in p.path


def en_pausa() -> bool:
    return time.monotonic() < _pausa_hasta


def _id(url: str) -> str:
    return urlparse(url).path.rstrip("/").split("/")[-1]


def _pedir(metodo, url, **kw):
    """Pedido a Google respetando el intervalo; 429 → pausa y _Limitado."""
    global _ultimo, _pausa_hasta
    with _candado:
        if en_pausa():
            raise _Limitado()
        espera = _ultimo + INTERVALO_S - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        _ultimo = time.monotonic()
    resp = metodo(url, timeout=TIMEOUT, **kw)
    if getattr(resp, "status_code", 200) == 429 or "google.com/sorry" in str(getattr(resp, "url", "")):
        _pausa_hasta = time.monotonic() + PAUSA_429_S
        raise _Limitado()
    return resp


def enlace_real(url: str, sesion=None):
    """Enlace del medio; "" si Google no lo tiene (no vale la pena reintentar); None si falló por ahora
    (pausa por 429, red caída…) y conviene reintentar más tarde. Nunca lanza."""
    if not es_de_google(url):
        return ""
    sesion = sesion or requests
    try:
        gid = _id(url)
        pagina = _pedir(sesion.get, f"https://news.google.com/articles/{gid}", headers=HEADERS).text
        firma, fecha = _FIRMA.search(pagina), _FECHA.search(pagina)
        if not firma or not fecha:
            return ""
        pedido = [[["Fbv4je", json.dumps(
            ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None,
                             None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
             gid, int(fecha.group(1)), firma.group(1)]), None, "generic"]]]
        resp = _pedir(sesion.post, _API, data=f"f.req={quote(json.dumps(pedido))}",
                      headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        datos = json.loads(resp.text.split("\n\n", 1)[1])
        real = json.loads(datos[0][2])[1]
        return real if urlparse(real).scheme in ("http", "https") else ""
    except (ValueError, IndexError, KeyError, TypeError):
        return ""    # respuesta con otra forma: Google no entrega este enlace
    except Exception:  # noqa: BLE001 — 429, red, timeout: se reintenta en otra corrida
        return None
