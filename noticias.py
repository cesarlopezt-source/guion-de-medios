from clusterer import agrupar
from config.personajes import PERSONAJES
from config.temas import TEMAS
from scorer import estrellas, puntuar

_ORDEN_TEMAS = list(TEMAS)
_ORDEN_PERSONAJES = list(PERSONAJES)


def _union_ordenada(listas, orden: list) -> list:
    presentes = {x for lista in listas for x in lista}
    return [x for x in orden if x in presentes]


def _noticia(cluster: list, puntaje: float) -> dict:
    temas = _union_ordenada((a["temas"] for a in cluster), _ORDEN_TEMAS)
    fuentes, vistas = [], set()
    for a in cluster:
        if a["fuente"] not in vistas:
            vistas.add(a["fuente"])
            fuentes.append({"nombre": a["fuente"], "url": a["url"]})
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


def filtrar(noticias: list, paises: set, temas: set, personajes: set) -> list:
    """País marcado Y algún tema marcado Y (si hay personajes marcados) algún personaje marcado."""
    return [
        n for n in noticias
        if n["pais"] in paises
        and temas.intersection(n["temas"])
        and (not personajes or personajes.intersection(n["personajes"]))
    ]


def ordenar(noticias: list, orden: str) -> list:
    if orden == "recientes":
        return sorted(noticias, key=lambda n: n["publicado"], reverse=True)
    return sorted(noticias, key=lambda n: (n["puntaje"], n["publicado"]), reverse=True)
