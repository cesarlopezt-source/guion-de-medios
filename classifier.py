import re

from config.paises import EL_SALVADOR_KEYWORDS, PAIS_KEYWORDS
from config.personajes import PERSONAJES
from config.temas import TEMAS
from texto import normalizar


def _patron(palabras: list) -> re.Pattern:
    alternativas = "|".join(re.escape(normalizar(p)) for p in palabras)
    return re.compile(rf"\b(?:{alternativas})\b")


_TEMAS = {tema: _patron(pal) for tema, pal in TEMAS.items()}
_PERSONAJES = {nombre: _patron(var) for nombre, var in PERSONAJES.items()}
_PAISES = {pais: _patron(pal) for pais, pal in PAIS_KEYWORDS.items()}
_SV = _patron(EL_SALVADOR_KEYWORDS)


def _pais_regional(texto: str) -> str:
    conteos = {pais: len(p.findall(texto)) for pais, p in _PAISES.items()}
    maximo = max(conteos.values())
    if maximo == 0 or list(conteos.values()).count(maximo) > 1:
        return "REG"
    return max(conteos, key=conteos.get)


def clasificar(articulo: dict) -> dict:
    """Devuelve una copia con temas, personajes y menciona_sv; resuelve el país de los regionales."""
    texto = normalizar(f"{articulo.get('titulo', '')} {articulo.get('resumen', '')}")
    resultado = dict(articulo)
    if resultado.get("pais") == "REG":
        resultado["pais"] = _pais_regional(texto)
    temas = [tema for tema, p in _TEMAS.items() if p.search(texto)]
    resultado["temas"] = temas or ["Otras"]
    resultado["personajes"] = [n for n, p in _PERSONAJES.items() if p.search(texto)]
    resultado["menciona_sv"] = resultado.get("pais") != "SV" and bool(_SV.search(texto))
    return resultado
