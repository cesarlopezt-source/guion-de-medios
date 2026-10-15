import html
import re
import unicodedata

_ETIQUETAS = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"\s+")


def normalizar(s: str) -> str:
    """Minúsculas y sin tildes, para comparar palabras clave."""
    descompuesto = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def limpiar_html(s: str) -> str:
    """Quita etiquetas HTML, decodifica entidades y colapsa espacios."""
    sin_etiquetas = _ETIQUETAS.sub(" ", s or "")
    texto = html.unescape(sin_etiquetas).replace("\xa0", " ")
    return _ESPACIOS.sub(" ", texto).strip()
