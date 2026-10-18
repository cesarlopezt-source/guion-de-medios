import re
from datetime import datetime

import ajustes
import ia
from config.paises import PAISES

MAX_NOTICIAS = 12
PALABRAS_POR_MINUTO = 150
MAX_PALABRAS = 750       # 5 minutos; si el guion se pasa de MAX_PALABRAS_TOLERADAS se pide acortarlo
MAX_PALABRAS_TOLERADAS = 850
INSTRUCCIONES = ajustes.RAIZ / "config" / "guion_instrucciones.md"
_MARCA = re.compile(r"^\s*\[[^\]]+\]\s*$")
MARCA_NOTAS = "[NOTAS DE APOYO]"


def contar_palabras(texto: str) -> int:
    """Palabras que se leen a cámara: sin las marcas ni las notas de apoyo del final."""
    hablado = texto.split(MARCA_NOTAS, 1)[0]
    return sum(len(linea.split()) for linea in hablado.splitlines() if not _MARCA.match(linea))


def _fecha(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(ajustes.ZONA_SV).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "sin fecha"


def minutos_estimados(palabras: int) -> float:
    return round(palabras / PALABRAS_POR_MINUTO, 1)


def _prompt(noticias: list, instrucciones: str) -> str:
    lineas = [
        "Eres el guionista de un programa de análisis en video que la presentadora leerá a cámara.",
        "Escribe UN solo guion corrido con estas noticias, siguiendo las instrucciones del programa.",
        "",
        "INSTRUCCIONES DEL PROGRAMA:",
        instrucciones.strip(),
        "",
        "REGLAS OBLIGATORIAS:",
        "- Los HECHOS salen SOLO de las noticias de abajo. No inventes cifras, fechas, nombres ni declaraciones.",
        "- El análisis, las preguntas y la lectura propia sí son tuyos, pero que se note qué es dato y qué es",
        "  interpretación, y no afirmes más de lo que la información permite.",
        "- Cita siempre el medio de cada noticia (\"según ...\") y la fecha del dato cuando importe.",
        "- No ataques, ridiculices ni acuses al Gobierno de El Salvador ni a sus funcionarios.",
        f"- Máximo {MAX_PALABRAS} palabras habladas en total (sin contar [NOTAS DE APOYO]). Es un límite:",
        "  con más noticias, menos detalle en cada una.",
        "- No uses subtítulos ni preguntas fijas repetidas en cada noticia; que suene a conversación.",
        "- Usa estas marcas de sección, cada una sola en su propia línea:",
        "  [APERTURA] al inicio; [NOTICIA n · País] antes de cada noticia; [TRANSICIÓN] entre noticias;",
        "  [CIERRE] para la despedida; y al final [NOTAS DE APOYO].",
        "- Fuera de las marcas, escribe solo el texto que se leerá en voz alta, excepto en [NOTAS DE APOYO].",
        "- [NOTAS DE APOYO] no se lee a cámara: por cada dato usado, una línea con el dato, el medio, la fecha",
        "  y cualquier aclaración o contexto útil para la presentadora. Texto plano, cada línea empieza con \"- \";",
        "  sin asteriscos ni negritas.",
        "",
        "NOTICIAS:",
    ]
    for i, n in enumerate(noticias, 1):
        medios = ", ".join(f["nombre"] for f in n.get("fuentes", []))
        lineas += [
            f"{i}. País: {PAISES.get(n.get('pais'), n.get('pais'))}",
            f"   Título: {n['titulo']}",
            f"   Fecha: {_fecha(n.get('publicado'))}",
            f"   Resumen: {(n.get('resumen') or '')[:600]}",
        ]
        if n.get("valoracion"):
            lineas.append(f"   Nota del editor: {n['valoracion']}")
        lineas += [f"   Temas: {', '.join(n.get('temas', []))}", f"   Medios: {medios}", ""]
    return "\n".join(lineas)


def _prompt_acortar(texto: str) -> str:
    return "\n".join([
        f"Este guion se pasa del límite. Acórtalo a un máximo de {MAX_PALABRAS} palabras habladas",
        "(sin contar [NOTAS DE APOYO]), manteniendo la voz, el análisis más valioso, las marcas de sección",
        "y las [NOTAS DE APOYO] completas al final. No agregues hechos nuevos. Devuelve solo el guion.",
        "",
        texto,
    ])


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
    if contar_palabras(texto) > MAX_PALABRAS_TOLERADAS:
        corto = ia.generar(_prompt_acortar(texto), ajustes.GEMINI_MODEL, client).strip()
        if _tiene_marcas(corto) and contar_palabras(corto) < contar_palabras(texto):
            texto = corto
    palabras = contar_palabras(texto)
    return {"texto": texto, "palabras": palabras, "minutos": minutos_estimados(palabras)}
