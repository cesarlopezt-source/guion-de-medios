import re
from datetime import timedelta
from difflib import SequenceMatcher

SIMILARITY_THRESHOLD = 0.70
VENTANA = timedelta(hours=48)
JACCARD_MINIMO = 0.3  # filtro barato por palabras antes de difflib
_PALABRA = re.compile(r"\w+")


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def agrupar(articulos: list) -> list:
    """Agrupa por similitud de títulos (difflib, umbral 0.70) entre artículos con ≤48 h de diferencia."""
    orden = sorted(articulos, key=lambda a: a["publicado"])
    titulos = [a["titulo"].lower() for a in orden]
    palabras = [set(_PALABRA.findall(t)) for t in titulos]
    usado = [False] * len(orden)
    grupos = []
    for i, art in enumerate(orden):
        if usado[i]:
            continue
        grupo = [art]
        usado[i] = True
        matcher = SequenceMatcher(None, titulos[i])
        for j in range(i + 1, len(orden)):
            if orden[j]["publicado"] - art["publicado"] > VENTANA:
                break
            if usado[j] or _jaccard(palabras[i], palabras[j]) < JACCARD_MINIMO:
                continue
            matcher.set_seq2(titulos[j])
            if (matcher.real_quick_ratio() >= SIMILARITY_THRESHOLD
                    and matcher.quick_ratio() >= SIMILARITY_THRESHOLD
                    and matcher.ratio() >= SIMILARITY_THRESHOLD):
                grupo.append(orden[j])
                usado[j] = True
        grupos.append(grupo)
    return grupos
