from config.regiones import REGIONES

# Orden de cercano a lejano: Centroamérica, Regional y luego el resto del mundo (config/regiones.py).
PAISES = {
    "SV": "El Salvador",
    "GT": "Guatemala",
    "HN": "Honduras",
    "NI": "Nicaragua",
    "CR": "Costa Rica",
    "PA": "Panamá",
    "REG": "Regional",
    **{codigo: r["nombre"] for codigo, r in REGIONES.items()},
}

# Para asignar país a las noticias de medios regionales.
PAIS_KEYWORDS = {
    "SV": ["el salvador", "salvadoreño", "salvadoreña", "salvadoreños", "san salvador", "bukele"],
    "GT": ["guatemala", "guatemalteco", "guatemalteca", "guatemaltecos", "arévalo"],
    "HN": ["honduras", "hondureño", "hondureña", "hondureños", "tegucigalpa", "san pedro sula"],
    "NI": ["nicaragua", "nicaragüense", "nicaragüenses", "managua", "ortega", "murillo"],
    "CR": ["costa rica", "costarricense", "costarricenses", "tico", "ticos", "san josé"],
    "PA": ["panamá", "panameño", "panameña", "panameños", "canal de panamá", "mulino"],
}

EL_SALVADOR_KEYWORDS = [
    "el salvador", "salvadoreño", "salvadoreña", "salvadoreños", "san salvador",
    "bukele", "cuscatlán",
    "nayib", "fmln", "farabundo martí", "nuevas ideas",
    "sonsonate", "ahuachapán", "usulután", "chalatenango", "morazán",
]
