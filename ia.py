import os
import time

from google import genai
from google.genai import errors

import ajustes

# Errores pasajeros de Gemini: saturación (503), cuota por minuto (429) y fallas del servidor.
REINTENTABLES = {429, 500, 502, 503, 504}
INTENTOS_POR_MODELO = 2
ESPERA_S = 3
_dormir = time.sleep


class ConfigError(Exception):
    """Falta configuración de Gemini (la API responde 503)."""


class IASaturada(RuntimeError):
    """Gemini siguió saturado con el modelo principal y con los de respaldo."""


def obtener_cliente():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ConfigError("GEMINI_API_KEY no configurada")
    return genai.Client(api_key=api_key)


def generar(prompt: str, modelo: str, client=None, respaldos=None) -> str:
    """Pide el texto a `modelo`; si está saturado reintenta y luego prueba los modelos de respaldo."""
    client = client or obtener_cliente()
    respaldos = ajustes.GEMINI_RESPALDOS if respaldos is None else respaldos
    modelos = [modelo] + [m for m in respaldos if m != modelo]
    for i, actual in enumerate(modelos):
        for intento in range(INTENTOS_POR_MODELO):
            try:
                return client.models.generate_content(model=actual, contents=prompt).text or ""
            except errors.APIError as e:
                if e.code not in REINTENTABLES:
                    if i == 0:
                        raise  # error real del pedido (clave, contenido…): se informa tal cual
                    break      # un respaldo que no existe o no está habilitado: se salta
                if intento + 1 < INTENTOS_POR_MODELO:
                    _dormir(ESPERA_S)
    raise IASaturada("Gemini está saturado en este momento (pasa a veces por unos minutos). "
                     "Espera un poco y vuelve a intentarlo.")
