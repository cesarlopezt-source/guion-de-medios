from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from collectors._comun import ahora, articulo, fecha_segura
from texto import limpiar_html


def _fecha(nodo):
    if nodo is None:
        return ahora()
    valor = nodo.get("datetime") or nodo.get_text().strip()
    try:
        return fecha_segura(datetime.fromisoformat(valor))
    except ValueError:
        return ahora()


def parsear(contenido: bytes, fuente: dict) -> list:
    sel = fuente["selectores"]
    sopa = BeautifulSoup(contenido, "html.parser")
    vistos = set()
    resultado = []
    for item in sopa.select(sel["item"]):
        nodo_titulo = item.select_one(sel["titulo"])
        nodo_enlace = item.select_one(sel["enlace"])
        if nodo_titulo is None or nodo_enlace is None or not nodo_enlace.get("href"):
            continue
        titulo = limpiar_html(nodo_titulo.get_text())
        url = urljoin(fuente["url"], nodo_enlace["href"])
        if not titulo or url in vistos:
            continue
        vistos.add(url)
        nodo_resumen = item.select_one(sel["resumen"]) if sel.get("resumen") else None
        resumen = limpiar_html(nodo_resumen.get_text()) if nodo_resumen else ""
        nodo_fecha = item.select_one(sel["fecha"]) if sel.get("fecha") else None
        resultado.append(articulo(titulo, resumen, url, fuente["nombre"], fuente["pais"], _fecha(nodo_fecha), "web"))
    return resultado
