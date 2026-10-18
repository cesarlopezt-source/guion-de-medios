import re

from config.organismos import ORGANISMOS
from config.paises import EL_SALVADOR_KEYWORDS, PAIS_KEYWORDS
from config.partidos import PARTIDOS
from config.personajes import PERSONAJES
from config.temas import TEMAS
from texto import normalizar


def _patron(palabras: list) -> re.Pattern:
    alternativas = "|".join(re.escape(normalizar(p)) for p in palabras)
    return re.compile(rf"\b(?:{alternativas})\b")


_TEMAS = {tema: _patron(pal) for tema, pal in TEMAS.items()}
_PERSONAJES = {nombre: _patron(var) for nombre, var in PERSONAJES.items()}


def _patron_partido(p: dict):
    """Devuelve una función texto_original → bool para un partido de config/partidos.py."""
    normal = _patron(p["texto"]) if p.get("texto") else None
    exactos = [re.compile(e) for e in p.get("exacto", [])]
    # Siglas en mayúsculas, pero no dentro de un titular todo en mayúsculas ("SELECTA GANA EN CASA").
    exactos += [re.compile(rf"(?<![A-ZÁÉÍÓÚÑ] )\b{re.escape(s)}\b(?! [A-ZÁÉÍÓÚÑ]{{2,}})") for s in p.get("siglas", [])]

    def buscar(original: str, normalizado: str) -> bool:
        return bool(normal and normal.search(normalizado)) or any(e.search(original) for e in exactos)
    return buscar


_PARTIDOS = {nombre: _patron_partido(p) for nombre, p in PARTIDOS.items()}
_ORGANISMOS = {nombre: _patron_partido(o) for nombre, o in ORGANISMOS.items()}
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
    original = f"{articulo.get('titulo', '')} {articulo.get('resumen', '')}"
    texto = normalizar(original)
    resultado = dict(articulo)
    if resultado.get("pais") == "REG":
        resultado["pais"] = _pais_regional(texto)
    temas = [tema for tema, p in _TEMAS.items() if p.search(texto)]
    resultado["temas"] = temas or ["Otras"]
    # Partidos y organismos van en la misma lista que los personajes (después de ellos); el portal los separa.
    resultado["personajes"] = ([n for n, p in _PERSONAJES.items() if p.search(texto)]
                               + [n for n, buscar in _PARTIDOS.items() if buscar(original, texto)]
                               + [n for n, buscar in _ORGANISMOS.items() if buscar(original, texto)])
    resultado["menciona_sv"] = resultado.get("pais") != "SV" and bool(_SV.search(texto))
    return resultado
