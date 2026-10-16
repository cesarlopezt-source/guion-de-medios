# Partidos políticos de El Salvador. Se guardan junto a los personajes de cada nota,
# pero en el portal tienen su propio menú.
#   texto:   variantes sin tildes ni mayúsculas, palabra completa (como en personajes.py).
#   siglas:  en mayúsculas exactas; no cuentan dentro de un titular escrito todo en mayúsculas.
#   exacto:  expresiones que distinguen mayúsculas, para nombres que también son palabras comunes.
#   busqueda: consulta en Google News (filtrada después a medios conocidos).
# Verificados 2026-10-15: con diputados en la Asamblea 2024-2027 Nuevas Ideas, ARENA, PCN, PDC y Vamos.
PARTIDOS = {
    "Nuevas Ideas": {"texto": ["nuevas ideas"], "busqueda": '"Nuevas Ideas"'},
    "ARENA": {"texto": ["alianza republicana nacionalista", "partido arena", "arenero", "areneros", "arenera", "areneras"],
              "siglas": ["ARENA"], "busqueda": '"partido ARENA"'},
    "FMLN": {"texto": ["fmln", "frente farabundo marti", "efemelenista", "efemelenistas"], "busqueda": '"FMLN"'},
    "GANA": {"texto": ["gran alianza por la unidad nacional", "partido gana"], "siglas": ["GANA"],
             "busqueda": '"partido GANA"'},
    "PCN": {"texto": ["partido de concertacion nacional"], "siglas": ["PCN"], "busqueda": '"PCN" El Salvador'},
    "PDC": {"texto": ["partido democrata cristiano"], "siglas": ["PDC"], "busqueda": '"PDC" El Salvador'},
    "Vamos": {"texto": ["partido vamos"],
              "exacto": [r"\b(?:[Dd]iputad[oa]s?|[Ff]racci[oó]n|[Bb]ancada|[Pp]artido|[Dd]e|[Dd]el) Vamos\b"],
              "busqueda": '"partido Vamos" El Salvador'},
    "Nuestro Tiempo": {"texto": ["partido nuestro tiempo"], "exacto": [r"\bNuestro Tiempo\b"],
                       "busqueda": '"Nuestro Tiempo" partido'},
}
