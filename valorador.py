import json

import ajustes
import ia


def _prompt(items: list) -> str:
    lineas = [
        "Eres un analista de noticias centroamericanas. Para cada noticia a continuación,",
        "escribe un resumen ejecutivo de exactamente 2 líneas que condense lo esencial",
        "para alguien que no leerá la noticia completa. Sé directo y objetivo.",
        "",
        "Responde SOLO con JSON válido en este formato:",
        '[{"titulo": "...", "valoracion": "línea 1. línea 2."}]',
        "",
        "Noticias:",
    ]
    for i, item in enumerate(items, 1):
        lineas.append(f'{i}. Título: "{item["titulo"]}"')
        lineas.append(f'   Resumen: "{(item.get("resumen") or "")[:300]}"')
        lineas.append("")
    return "\n".join(lineas)


def _parsear(texto: str) -> list:
    inicio, fin = texto.find("["), texto.rfind("]") + 1
    if inicio == -1 or fin == 0:
        raise ValueError("No hay un arreglo JSON en la respuesta")
    return json.loads(texto[inicio:fin])


def generar_valoraciones(items: list, client=None) -> list:
    if not items:
        return []
    client = client or ia.obtener_cliente()
    prompt = _prompt(items)
    texto = ""
    for _ in range(2):
        texto = ia.generar(prompt, ajustes.GEMINI_MODEL_VALORAR, client)
        try:
            return _parsear(texto)
        except (ValueError, json.JSONDecodeError):
            continue
    raise RuntimeError(f"No se pudo leer la respuesta de Gemini: {texto[:200]}")
