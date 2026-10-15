import feedparser

from collectors._comun import articulo, fecha_de_entrada
from config.fuentes import fuente_por_dominio
from texto import limpiar_html, normalizar


def parsear(contenido: bytes, fuente: dict) -> list:
    feed = feedparser.parse(contenido)
    resultado = []
    for e in feed.entries:
        titulo = limpiar_html(e.get("title", ""))
        url = e.get("link", "")
        source = e.get("source") or {}
        nombre_google = source.get("title") or ""
        conocida = fuente_por_dominio(source.get("href"))
        if fuente.get("solo_medios_conocidos") and conocida is None:
            continue
        medio = fuente.get("medio") or (conocida or {}).get("nombre") or nombre_google or fuente["nombre"]
        pais = conocida["pais"] if fuente.get("solo_medios_conocidos") else fuente["pais"]
        for nombre in {nombre_google, medio}:
            if nombre and titulo.endswith(f" - {nombre}"):
                titulo = titulo[: -len(nombre) - 3].strip()
        # Google a veces publica la portada del medio como "Medio - Medio": no es una noticia.
        if not titulo or not url or normalizar(titulo) in {normalizar(nombre_google), normalizar(medio)}:
            continue
        # La descripción de Google News solo repite el titular y el medio.
        resultado.append(articulo(titulo, "", url, medio, pais, fecha_de_entrada(e), "google_news"))
    return resultado
