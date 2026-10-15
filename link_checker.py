from concurrent.futures import ThreadPoolExecutor

import requests


def check_url(url: str, timeout: float = 5.0) -> bool:
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        return 200 <= resp.status_code < 400
    except requests.RequestException:
        return False


def check_urls(urls: list) -> dict:
    unique_urls = list(dict.fromkeys(urls))
    if not unique_urls:
        return {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(check_url, unique_urls))
    return dict(zip(unique_urls, results))
