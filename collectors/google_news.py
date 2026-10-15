import feedparser

from collectors._comun import articulo, fecha_de_entrada
from texto import limpiar_html


def parsear(contenido: bytes, fuente: dict) -> list:
    feed = feedparser.parse(contenido)
    resultado = []
    for e in feed.entries:
        titulo = limpiar_html(e.get("title", ""))
        url = e.get("link", "")
        if not titulo or not url:
            continue
        medio = (e.get("source") or {}).get("title") or fuente["nombre"]
        sufijo = f" - {medio}"
        if titulo.endswith(sufijo):
            titulo = titulo[: -len(sufijo)].strip()
        # La descripción de Google News solo repite el titular y el medio.
        resultado.append(articulo(titulo, "", url, medio, fuente["pais"], fecha_de_entrada(e), "google_news"))
    return resultado
