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
        resultado.append(articulo(
            titulo, limpiar_html(e.get("summary", "")), url, fuente["nombre"],
            fuente["pais"], fecha_de_entrada(e), "rss",
        ))
    return resultado
