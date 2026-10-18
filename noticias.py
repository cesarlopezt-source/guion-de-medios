import re

from clusterer import agrupar
from config.fuentes import TITULAR_EEUU
from config.partidos import PARTIDOS
from config.personajes import PERSONAJES
from config.temas import TEMAS
from scorer import estrellas, puntuar
from texto import normalizar

_ORDEN_TEMAS = list(TEMAS)
_ORDEN_PERSONAJES = list(PERSONAJES) + list(PARTIDOS)


def _union_ordenada(listas, orden: list) -> list:
    presentes = {x for lista in listas for x in lista}
    return [x for x in orden if x in presentes]


def _noticia(cluster: list, puntaje: float) -> dict:
    temas = _union_ordenada((a["temas"] for a in cluster), _ORDEN_TEMAS)
    fuentes, vistas = [], set()
    for a in cluster:
        if a["fuente"] not in vistas:
            vistas.add(a["fuente"])
            # Si es de Google News y ya se conoce el enlace real del medio, se muestra ese.
            fuentes.append({"nombre": a["fuente"], "url": a.get("enlace") or a["url"]})
    return {
        "titulo": max(cluster, key=lambda a: len(a["titulo"]))["titulo"],
        "resumen": max(cluster, key=lambda a: len(a.get("resumen") or ""))["resumen"] or "",
        "pais": cluster[0]["pais"],
        "temas": temas or ["Otras"],
        "personajes": _union_ordenada((a["personajes"] for a in cluster), _ORDEN_PERSONAJES),
        "menciona_sv": any(a["menciona_sv"] for a in cluster),
        "fuentes": fuentes,
        "publicado": max(a["publicado"] for a in cluster).isoformat(),
        "n_fuentes": len(fuentes),
        "puntaje": puntaje,
    }


def construir_noticias(articulos: list) -> list:
    """Agrupa por país, puntúa cada grupo y asigna estrellas relativas al máximo de la corrida."""
    por_pais = {}
    for a in articulos:
        por_pais.setdefault(a["pais"], []).append(a)
    clusters = [c for grupo in por_pais.values() for c in agrupar(grupo)]
    puntajes = [puntuar(c) for c in clusters]
    maximo = max(puntajes, default=0.0)
    resultado = []
    for cluster, puntaje in zip(clusters, puntajes):
        n = _noticia(cluster, puntaje)
        n["estrellas"] = estrellas(puntaje, maximo)
        resultado.append(n)
    return resultado


AMBITOS = ["Nacionales", "Internacionales"]
_EEUU = [re.compile(rf"\b(?:{'|'.join(re.escape(normalizar(p)) for p in grupo)})\b") for grupo in TITULAR_EEUU]


def trata_de_eeuu(noticia: dict) -> bool:
    """El titular nombra a EE. UU. y también a El Salvador o la región (aranceles, TPS, deportaciones…)."""
    titulo = normalizar(noticia["titulo"])
    return all(p.search(titulo) for p in _EEUU)


def _pais_marcado(noticia: dict, paises: set) -> bool:
    # "Estados Unidos" reúne las notas de su relación con la región, sea cual sea el medio que las publicó.
    return noticia["pais"] in paises or ("US" in paises and trata_de_eeuu(noticia))


def ambitos_de(noticia: dict) -> set:
    """Nacionales = de El Salvador o que lo mencionan; Internacionales = de cualquier otro país."""
    resultado = set()
    if noticia["pais"] == "SV" or noticia.get("menciona_sv"):
        resultado.add("Nacionales")
    if noticia["pais"] != "SV":
        resultado.add("Internacionales")
    return resultado


def filtrar(noticias: list, paises: set, temas: set, personajes: set, partidos: set = frozenset(),
            ambitos: set = frozenset()) -> list:
    """País marcado Y algún tema marcado Y (si hay personajes marcados) algún personaje marcado
    Y (si hay partidos marcados) algún partido marcado Y (si hay ámbitos marcados) algún ámbito marcado."""
    return [
        n for n in noticias
        if _pais_marcado(n, paises)
        and temas.intersection(n["temas"])
        and (not personajes or personajes.intersection(n["personajes"]))
        and (not partidos or partidos.intersection(n["personajes"]))
        and (not ambitos or ambitos.intersection(ambitos_de(n)))
    ]


def ordenar(noticias: list, orden: str) -> list:
    if orden == "recientes":
        return sorted(noticias, key=lambda n: n["publicado"], reverse=True)
    return sorted(noticias, key=lambda n: (n["puntaje"], n["publicado"]), reverse=True)
