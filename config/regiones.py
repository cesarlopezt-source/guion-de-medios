# Regiones fuera de Centroamérica. Solo interesan las noticias que tocan a El Salvador o a Centroamérica
# (economía, política, finanzas, migración…), por eso cada búsqueda exige en el titular la región
# Y El Salvador/Centroamérica.
#   es:          palabras de la región en español (sin tildes ni mayúsculas, palabra completa).
#   busqueda_es: consulta en Google News en español (se le agrega "El Salvador").
#   extranjero:  búsquedas en el idioma del lugar; los titulares se traducen al español.
#                (idioma, país de Google News, consulta, palabras de la región en ese idioma)

SV_ES = ["el salvador", "salvadoreño", "salvadoreña", "salvadoreños", "salvadoreñas", "bukele",
         "centroamérica", "centroamericano", "centroamericana", "centroamericanos", "centroamericanas",
         "triángulo norte", "sica"]
SV_EN = ["el salvador", "salvadoran", "salvadorans", "salvadorian", "bukele", "central america",
         "central american", "central americans"]
SV_PT = ["el salvador", "salvadorenho", "salvadorenha", "salvadorenhos", "bukele", "américa central",
         "centro-americano", "centro-americana"]

REGIONES = {
    "US": {
        "nombre": "Estados Unidos",
        "es": ["estados unidos", "ee.uu", "eeuu", "ee. uu", "estadounidense", "estadounidenses", "trump",
               "washington", "casa blanca", "departamento de estado", "marco rubio", "rubio", "ice", "tps",
               "reserva federal"],
        "busqueda_es": "aranceles OR remesas OR deportaciones OR TPS OR \"Estados Unidos\" OR Trump",
        "extranjero": [("en", "US", "\"El Salvador\" tariffs OR remittances OR deportation OR TPS OR Trump",
                        ["united states", "u.s", "trump", "washington", "white house", "state department",
                         "rubio", "ice", "tps", "deportation", "deportations", "tariff", "tariffs", "remittances",
                         "federal reserve", "american"])],
    },
    "CAN": {
        "nombre": "Canadá",
        "es": ["canadá", "canadiense", "canadienses", "ottawa", "toronto", "montreal", "vancouver", "carney"],
        "busqueda_es": "Canadá",
        "extranjero": [("en", "CA", "\"El Salvador\" Canada", ["canada", "canadian", "canadians", "ottawa",
                                                               "toronto", "montreal", "vancouver", "carney"])],
    },
    "MX": {
        "nombre": "México",
        "es": ["méxico", "mexicano", "mexicana", "mexicanos", "mexicanas", "sheinbaum", "cdmx", "pemex"],
        "busqueda_es": "México OR mexicano",
        "extranjero": [],
    },
    "CAR": {
        "nombre": "Caribe",
        "es": ["caribe", "caribeño", "caribeña", "caribeños", "cuba", "cubano", "cubana", "cubanos",
               "república dominicana", "dominicano", "dominicana", "dominicanos", "haití", "haitiano", "haitianos",
               "puerto rico", "puertorriqueño", "jamaica", "caricom", "trinidad y tobago", "bahamas", "barbados"],
        "busqueda_es": "Caribe OR Cuba OR \"República Dominicana\" OR Haití OR \"Puerto Rico\"",
        "extranjero": [],
    },
    "SUD": {
        "nombre": "Sudamérica",
        "es": ["sudamérica", "suramérica", "sudamericano", "suramericano", "brasil", "brasileño", "brasileña",
               "argentina", "argentino", "milei", "lula", "colombia", "colombiano", "colombiana", "petro",
               "venezuela", "venezolano", "venezolana", "venezolanos", "maduro", "chile", "chileno", "chilena",
               "perú", "peruano", "peruana", "ecuador", "ecuatoriano", "ecuatoriana", "noboa", "bolivia",
               "boliviano", "uruguay", "uruguayo", "paraguay", "paraguayo", "mercosur"],
        "busqueda_es": "Colombia OR Venezuela OR Argentina OR Brasil OR Chile OR Perú OR Ecuador",
        "extranjero": [("pt", "BR", "\"El Salvador\"", ["brasil", "brasileiro", "brasileira", "lula", "mercosul",
                                                        "américa do sul", "sul-americano"])],
    },
    "UE": {
        "nombre": "Unión Europea",
        "es": ["unión europea", "comisión europea", "parlamento europeo", "consejo europeo", "bruselas",
               "eurozona", "banco central europeo", "bce", "von der leyen", "ue"],
        "busqueda_es": "\"Unión Europea\" OR UE OR \"Comisión Europea\"",
        "extranjero": [("en", "BE", "\"El Salvador\" \"European Union\" OR EU OR \"European Commission\"",
                        ["european union", "european commission", "european parliament", "brussels",
                         "eurozone", "european central bank", "von der leyen", "eu"])],
    },
    "EUR": {
        "nombre": "Europa",
        "es": ["europa", "europeo", "europea", "europeos", "europeas", "españa", "madrid", "alemania", "alemán",
               "alemana", "berlín", "francia", "francés", "francesa", "parís", "italia", "italiano", "italiana",
               "roma", "reino unido", "británico", "británica", "londres", "portugal", "lisboa", "países bajos",
               "holanda", "bélgica", "suiza", "suecia", "noruega", "dinamarca", "finlandia", "polonia", "austria",
               "irlanda", "grecia", "ucrania", "ucraniano", "rusia", "ruso", "rusa", "putin", "otan", "kremlin",
               "vaticano", "papa león"],
        "busqueda_es": "Europa OR España OR Alemania OR Francia OR Italia OR \"Reino Unido\" OR Rusia OR Ucrania",
        "extranjero": [("en", "GB", "\"El Salvador\" Europe OR Spain OR Germany OR France OR Italy OR Britain",
                        ["europe", "european", "spain", "spanish", "madrid", "germany", "german", "berlin",
                         "france", "french", "paris", "italy", "italian", "rome", "britain", "british", "uk",
                         "london", "portugal", "netherlands", "dutch", "belgium", "switzerland", "sweden",
                         "norway", "poland", "ukraine", "russia", "russian", "putin", "nato", "vatican"])],
    },
    "ASI": {
        "nombre": "Asia",
        "es": ["asia", "asiático", "asiática", "china", "chino", "chinos", "pekín", "beijing",
               "xi jinping", "japón", "japonés", "japonesa", "tokio", "corea", "coreano", "coreana", "seúl",
               "taiwán", "taiwanés", "india", "nueva delhi", "vietnam", "singapur", "indonesia", "filipinas",
               "tailandia", "malasia", "hong kong"],
        "busqueda_es": "China OR Japón OR Corea OR Taiwán OR India OR Asia",
        "extranjero": [("en", "US", "\"El Salvador\" China OR Japan OR Korea OR Taiwan OR India OR Asia",
                        ["asia", "asian", "china", "chinese", "beijing", "xi jinping", "japan", "japanese",
                         "tokyo", "korea", "korean", "seoul", "taiwan", "taiwanese", "india", "indian",
                         "vietnam", "singapore", "indonesia", "philippines", "thailand", "hong kong"])],
    },
    "MO": {
        "nombre": "Medio Oriente",
        "es": ["medio oriente", "oriente medio", "oriente próximo", "israel", "israelí", "israelíes",
               "palestina", "palestino", "palestinos", "gaza", "cisjordania", "irán", "iraní", "arabia saudita",
               "saudí", "emiratos árabes", "emiratos", "catar", "qatar", "dubái", "abu dabi", "turquía", "turco",
               "líbano", "siria", "irak", "jordania", "egipto", "kuwait", "omán", "hamás", "hezbolá"],
        "busqueda_es": "Israel OR Irán OR \"Arabia Saudita\" OR Emiratos OR Catar OR Turquía OR \"Medio Oriente\"",
        "extranjero": [("en", "US", "\"El Salvador\" Israel OR Iran OR Saudi OR Emirates OR Qatar OR Turkey",
                        ["middle east", "israel", "israeli", "palestine", "palestinian", "gaza", "iran",
                         "iranian", "saudi", "emirates", "uae", "qatar", "qatari", "dubai", "abu dhabi",
                         "turkey", "turkish", "lebanon", "syria", "iraq", "jordan", "egypt", "kuwait"])],
    },
}

SV_POR_IDIOMA = {"es": SV_ES, "en": SV_EN, "pt": SV_PT}
