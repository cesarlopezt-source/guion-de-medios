import re

import ajustes
import ia
from config.paises import PAISES

MAX_NOTICIAS = 12
PALABRAS_POR_MINUTO = 150
INSTRUCCIONES = ajustes.RAIZ / "config" / "guion_instrucciones.md"
_MARCA = re.compile(r"^\s*\[[^\]]+\]\s*$")


def contar_palabras(texto: str) -> int:
    return sum(len(linea.split()) for linea in texto.splitlines() if not _MARCA.match(linea))


def minutos_estimados(palabras: int) -> float:
    return round(palabras / PALABRAS_POR_MINUTO, 1)


def _prompt(noticias: list, instrucciones: str) -> str:
    lineas = [
        "Eres el guionista de un noticiero en video que el presentador leerá a cámara.",
        "Escribe UN solo guion corrido con estas noticias, siguiendo las instrucciones del programa.",
        "",
        "INSTRUCCIONES DEL PROGRAMA:",
        instrucciones.strip(),
        "",
        "REGLAS OBLIGATORIAS:",
        "- Usa SOLO la información de las noticias de abajo. No inventes cifras, fechas ni declaraciones.",
        "- No agregues opiniones ni adjetivos valorativos que no estén en la noticia.",
        "- Cita siempre el medio de cada noticia (\"según ...\").",
        "- Usa estas marcas de sección, cada una sola en su propia línea:",
        "  [APERTURA] al inicio; [NOTICIA n · País] antes de cada noticia; [TRANSICIÓN] entre noticias;",
        "  [CIERRE] al final.",
        "- Fuera de las marcas, escribe solo el texto que se leerá en voz alta.",
        "",
        "NOTICIAS:",
    ]
    for i, n in enumerate(noticias, 1):
        medios = ", ".join(f["nombre"] for f in n.get("fuentes", []))
        lineas += [
            f"{i}. País: {PAISES.get(n.get('pais'), n.get('pais'))}",
            f"   Título: {n['titulo']}",
            f"   Resumen: {(n.get('resumen') or '')[:600]}",
        ]
        if n.get("valoracion"):
            lineas.append(f"   Nota del editor: {n['valoracion']}")
        lineas += [f"   Temas: {', '.join(n.get('temas', []))}", f"   Medios: {medios}", ""]
    return "\n".join(lineas)


def _tiene_marcas(texto: str) -> bool:
    return "[APERTURA]" in texto and "[CIERRE]" in texto


def generar_guion(noticias: list, instrucciones: str = None, client=None) -> dict:
    if not 1 <= len(noticias) <= MAX_NOTICIAS:
        raise ValueError(f"Selecciona entre 1 y {MAX_NOTICIAS} noticias para el guion.")
    if instrucciones is None:
        instrucciones = INSTRUCCIONES.read_text(encoding="utf-8")
    client = client or ia.obtener_cliente()
    prompt = _prompt(noticias, instrucciones)
    texto = ""
    for _ in range(2):
        texto = ia.generar(prompt, ajustes.GEMINI_MODEL, client).strip()
        if _tiene_marcas(texto):
            break
    palabras = contar_palabras(texto)
    return {"texto": texto, "palabras": palabras, "minutos": minutos_estimados(palabras)}
