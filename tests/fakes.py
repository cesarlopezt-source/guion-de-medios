class _Respuesta:
    def __init__(self, text):
        self.text = text


class ClienteFalso:
    """Imita google.genai.Client: devuelve las respuestas en orden y guarda los prompts."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.prompts = []
        self.modelos = []
        self.models = self

    def generate_content(self, model, contents):
        self.modelos.append(model)
        self.prompts.append(contents)
        return _Respuesta(self.respuestas.pop(0))


N1 = {"titulo": "Remesas crecen 5%", "resumen": "Las remesas suben.", "pais": "SV", "temas": ["Economía"],
      "personajes": [], "fuentes": [{"nombre": "La Prensa Gráfica", "url": "https://lpg/1"}],
      "publicado": "2026-10-14T16:00:00+00:00", "n_fuentes": 1, "estrellas": 4, "menciona_sv": False}
N2 = {**N1, "titulo": "Exportaciones de café", "pais": "GT", "temas": ["Economía", "Inversión"],
      "fuentes": [{"nombre": "Prensa Libre", "url": "https://pl/2"}]}
GUION_OK = "[APERTURA]\nHola a todos.\n[NOTICIA 1 · El Salvador]\nSegún La Prensa Gráfica las remesas suben.\n[CIERRE]\nHasta pronto."
