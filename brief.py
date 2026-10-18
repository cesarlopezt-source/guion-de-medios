"""Mini brief: un resumen corto por noticia (qué pasó y por qué importa), un análisis general del conjunto, o ambos.
Es otra opción aparte del guion: un documento para leer, no para grabar."""
import json

import ajustes
import ia
from config.paises import PAISES

MAX_NOTICIAS = 40
MODOS = {"brief", "analisis", "ambos"}
MARCA_ANALISIS = "[ANÁLISIS GENERAL]"


def _prompt(noticias: list, modo: str) -> str:
    pide = {
        "brief": 'Para CADA noticia escribe un mini brief de 2 a 3 líneas: qué pasó y por qué importa. '
                 'Deja "analisis" vacío.',
        "analisis": 'Escribe en "analisis" un análisis general de 3 a 5 párrafos cortos sobre el conjunto: '
                    'tendencias, riesgos, oportunidades y qué vigilar. Deja "briefs" como lista vacía.',
        "ambos": 'Para CADA noticia escribe un mini brief de 2 a 3 líneas (qué pasó y por qué importa) y, '
                 'además, en "analisis" un análisis general de 3 a 5 párrafos cortos sobre el conjunto: '
                 'tendencias, riesgos, oportunidades y qué vigilar.',
    }[modo]
    lineas = [
        "Eres un analista de noticias de El Salvador y Centroamérica que prepara un informe ejecutivo.",
        pide,
        "Usa SOLO la información de las noticias de abajo. No inventes cifras, fechas ni declaraciones.",
        "Escribe en español, directo y objetivo.",
        "",
        "Responde SOLO con JSON válido en este formato:",
        '{"analisis": "párrafo 1\\n\\npárrafo 2", "briefs": [{"n": 1, "brief": "..."}]}',
        "",
        "NOTICIAS:",
    ]
    for i, n in enumerate(noticias, 1):
        lineas += [
            f"{i}. País: {PAISES.get(n.get('pais'), n.get('pais'))}",
            f"   Título: {n['titulo']}",
            f"   Resumen: {(n.get('resumen') or '')[:500]}",
            f"   Temas: {', '.join(n.get('temas', []))}",
            "",
        ]
    return "\n".join(lineas)


def _parsear(texto: str) -> dict:
    inicio, fin = texto.find("{"), texto.rfind("}") + 1
    if inicio == -1 or fin == 0:
        raise ValueError("No hay un objeto JSON en la respuesta")
    datos = json.loads(texto[inicio:fin])
    return {"analisis": str(datos.get("analisis") or "").strip(),
            "briefs": {int(b["n"]): str(b.get("brief") or "").strip() for b in datos.get("briefs") or []}}


def armar_texto(noticias: list, datos: dict, modo: str) -> str:
    """Texto editable con marcas [..] para los títulos y una línea "- Medio: enlace" por fuente."""
    partes = []
    if modo in ("analisis", "ambos") and datos["analisis"]:
        partes.append(f"{MARCA_ANALISIS}\n{datos['analisis']}")
    if modo in ("brief", "ambos"):
        for i, n in enumerate(noticias, 1):
            pais = PAISES.get(n.get("pais"), n.get("pais"))
            bloque = [f"[{i} · {pais}]", n["titulo"]]
            if datos["briefs"].get(i):
                bloque.append(datos["briefs"][i])
            bloque += [f"- {f['nombre']}: {f['url']}" for f in n.get("fuentes", [])]
            partes.append("\n".join(bloque))
    return "\n\n".join(partes)


def generar_brief(noticias: list, modo: str = "ambos", client=None) -> dict:
    if modo not in MODOS:
        raise ValueError("Modo inválido: usa brief, analisis o ambos.")
    if not 1 <= len(noticias) <= MAX_NOTICIAS:
        raise ValueError(f"Selecciona entre 1 y {MAX_NOTICIAS} noticias para el mini brief.")
    client = client or ia.obtener_cliente()
    prompt = _prompt(noticias, modo)
    texto = ""
    for _ in range(2):
        texto = ia.generar(prompt, ajustes.GEMINI_MODEL, client)
        try:
            return {"texto": armar_texto(noticias, _parsear(texto), modo)}
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
    raise RuntimeError(f"No se pudo leer la respuesta de Gemini: {texto[:200]}")
