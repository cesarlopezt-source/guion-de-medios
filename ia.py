import os

from google import genai


class ConfigError(Exception):
    """Falta configuración de Gemini (la API responde 503)."""


def obtener_cliente():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ConfigError("GEMINI_API_KEY no configurada")
    return genai.Client(api_key=api_key)


def generar(prompt: str, modelo: str, client=None) -> str:
    client = client or obtener_cliente()
    return client.models.generate_content(model=modelo, contents=prompt).text or ""
