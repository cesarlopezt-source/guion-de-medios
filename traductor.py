"""Traduce al español los titulares de las búsquedas en otros idiomas (inglés, portugués) con Gemini."""
import json
import logging

import ajustes
import ia

log = logging.getLogger("traductor")
TANDA = 40


def _prompt(titulos: list) -> str:
    return "\n".join([
        "Traduce al español neutro (latinoamericano) estos titulares de noticias.",
        "Conserva nombres propios, siglas y cifras. No agregues nada.",
        "Responde SOLO con un arreglo JSON de textos, en el mismo orden y con la misma cantidad.",
        "",
        json.dumps(titulos, ensure_ascii=False),
    ])


def _traducir_tanda(titulos: list, client) -> list:
    texto = ia.generar(_prompt(titulos), ajustes.GEMINI_MODEL_VALORAR, client)
    inicio, fin = texto.find("["), texto.rfind("]") + 1
    traducidos = json.loads(texto[inicio:fin]) if inicio != -1 and fin else []
    if len(traducidos) != len(titulos) or not all(isinstance(t, str) and t.strip() for t in traducidos):
        raise ValueError("La traducción no trae un titular por cada original")
    return [t.strip() for t in traducidos]


def traducir(articulos: list, client=None) -> None:
    """Cambia en su lugar el titular de cada artículo por su traducción. Si Gemini falla, se queda el original."""
    if not articulos:
        return
    try:
        client = client or ia.obtener_cliente()
    except ia.ConfigError:
        log.warning("Sin GEMINI_API_KEY: los titulares en otros idiomas quedan sin traducir")
        return
    for i in range(0, len(articulos), TANDA):
        tanda = articulos[i:i + TANDA]
        try:
            for a, titulo in zip(tanda, _traducir_tanda([a["titulo"] for a in tanda], client)):
                a["titulo"] = titulo
        except Exception as e:  # noqa: BLE001 — una tanda sin traducir no detiene la corrida
            log.warning("No se pudo traducir una tanda de titulares: %s", str(e)[:200])
