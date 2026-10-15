"""Verifica si los enlaces de noticias archivadas siguen activos. Lo usa el watcher, no el portal."""
from concurrent.futures import ThreadPoolExecutor

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
}
BLOQUEO = {403, 405, 429}


def check_url(url: str, timeout: float = 8.0):
    """True si responde 2xx/3xx; False si 404/410 o falla la red; None si el sitio bloquea la verificación."""
    try:
        resp = requests.head(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code in BLOQUEO:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, stream=True)
            resp.close()
    except requests.RequestException:
        return False
    if 200 <= resp.status_code < 400:
        return True
    if resp.status_code in BLOQUEO:
        return None
    return False


def check_urls(urls: list) -> dict:
    unicas = list(dict.fromkeys(urls))
    if not unicas:
        return {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        return dict(zip(unicas, ex.map(check_url, unicas)))
