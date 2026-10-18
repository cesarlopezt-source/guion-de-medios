from urllib.parse import quote_plus, urlparse

from config.organismos import ORGANISMOS
from config.paises import PAIS_KEYWORDS
from config.partidos import PARTIDOS
from config.personajes import PERSONAJES
from config.regiones import REGIONES, SV_ES, SV_POR_IDIOMA

# Lectura web genérica: sirve para portadas que usan <article> con titular en h2/h3.
_WEB_ARTICLE = {"item": "article", "titulo": "h2, h3", "enlace": "h2 a[href], h3 a[href], a[href]"}
_WEB_TITULARES = {"item": "h2, h3", "titulo": "a", "enlace": "a[href]"}


def _medio(nombre, pais, dominio, tipo, url=None, activa=True, selectores=None):
    """Un medio. `activa` controla la lectura directa (rss/web); Google News cubre a todos por `dominio`."""
    fuente = {"nombre": nombre, "pais": pais, "dominio": dominio, "tipo": tipo, "url": url, "activa": activa}
    if selectores:
        fuente["selectores"] = selectores
    return fuente


# Verificado contra la red el 2026-10-15 (scripts/verificar_fuentes.py).
FUENTES = [
    # El Salvador
    _medio("La Prensa Gráfica", "SV", "laprensagrafica.com", "rss", activa=False),  # 403 al RSS y a la portada
    _medio("El Diario de Hoy", "SV", "elsalvador.com", "rss", "https://www.elsalvador.com/rss.xml"),
    _medio("Diario El Mundo", "SV", "diario.elmundo.sv", "rss", activa=False),  # sin RSS; portada con JS
    _medio("Diario Co Latino", "SV", "diariocolatino.com", "rss", "https://www.diariocolatino.com/feed/"),
    _medio("El Faro", "SV", "elfaro.net", "rss", activa=False),  # sin RSS; portada con JS
    _medio("Diario El Salvador", "SV", "diarioelsalvador.com", "rss", "https://diarioelsalvador.com/rss.xml"),
    _medio("La Página", "SV", "lapagina.com.sv", "rss", "https://www.lapagina.com.sv/feed/"),
    _medio("Revista Factum", "SV", "revistafactum.com", "rss", "https://www.revistafactum.com/feed/"),
    _medio("GatoEncerrado", "SV", "gatoencerrado.news", "rss", "https://gatoencerrado.news/feed/"),
    # Guatemala
    _medio("Prensa Libre", "GT", "prensalibre.com", "rss", "https://www.prensalibre.com/feed/"),
    _medio("Soy502", "GT", "soy502.com", "rss", activa=False),  # RSS vacío; portada con JS
    _medio("República", "GT", "republica.gt", "rss", "https://republica.gt/feed"),
    _medio("La Hora GT", "GT", "lahora.gt", "rss", "https://lahora.gt/feed/"),
    _medio("Plaza Pública", "GT", "plazapublica.com.gt", "rss", "https://plazapublica.com.gt/feed/"),
    _medio("Agencia Ocote", "GT", "agenciaocote.com", "rss", "https://www.agenciaocote.com/feed/"),
    # Honduras
    _medio("La Prensa HN", "HN", "laprensa.hn", "web", "https://www.laprensa.hn/", selectores=_WEB_ARTICLE),
    _medio("El Heraldo", "HN", "elheraldo.hn", "web", "https://www.elheraldo.hn/", selectores=_WEB_ARTICLE),
    _medio("Proceso Digital", "HN", "proceso.hn", "rss", "https://proceso.hn/feed/"),
    _medio("La Tribuna", "HN", "latribuna.hn", "rss", activa=False),  # 403
    _medio("Criterio.hn", "HN", "criterio.hn", "rss", "https://criterio.hn/feed/"),
    _medio("Contracorriente", "HN", "contracorriente.red", "rss", "https://contracorriente.red/feed/"),
    # Nicaragua
    _medio("La Prensa NI", "NI", "laprensani.com", "web", "https://www.laprensani.com/", selectores=_WEB_ARTICLE),
    _medio("Confidencial", "NI", "confidencial.digital", "rss", "https://confidencial.digital/feed/"),
    _medio("100% Noticias", "NI", "100noticias.com.ni", "rss", activa=False),  # dominio no resuelve
    _medio("Artículo 66", "NI", "articulo66.com", "rss", activa=False),  # 403
    _medio("Divergentes", "NI", "divergentes.com", "rss", "https://www.divergentes.com/feed/"),
    _medio("El 19 Digital", "NI", "el19digital.com", "rss", activa=False),  # 403
    # Costa Rica
    _medio("La Nación", "CR", "nacion.com", "rss", "https://www.nacion.com/arc/outboundfeeds/rss/?outputType=xml"),
    _medio("CRHoy", "CR", "crhoy.com", "rss", activa=False),  # RSS 404; portada con JS
    _medio("El Financiero CR", "CR", "elfinancierocr.com", "rss",
           "https://www.elfinancierocr.com/arc/outboundfeeds/rss/?outputType=xml"),
    _medio("Teletica", "CR", "teletica.com", "rss", activa=False),  # RSS vacío; portada con JS
    _medio("Delfino", "CR", "delfino.cr", "rss", "https://delfino.cr/feed"),
    _medio("Semanario Universidad", "CR", "semanariouniversidad.com", "rss", "https://semanariouniversidad.com/feed/"),
    # Panamá
    _medio("La Prensa PA", "PA", "prensa.com", "rss", "https://www.prensa.com/arc/outboundfeeds/rss/?outputType=xml"),
    _medio("La Estrella de Panamá", "PA", "laestrella.com.pa", "web", "https://www.laestrella.com.pa/",
           selectores=_WEB_ARTICLE),
    _medio("Panamá América", "PA", "panamaamerica.com.pa", "rss", "https://www.panamaamerica.com.pa/rss.xml"),
    _medio("TVN Noticias", "PA", "tvn-2.com", "rss", "https://www.tvn-2.com/rss"),
    _medio("Telemetro", "PA", "telemetro.com", "web", "https://www.telemetro.com/", selectores=_WEB_ARTICLE),
    # Regionales
    _medio("Estrategia & Negocios", "REG", "estrategiaynegocios.net", "rss", activa=False),  # certificado SSL inválido
    _medio("Revista Summa", "REG", "revistasumma.com", "rss", activa=False),  # 403
    _medio("Forbes Centroamérica", "REG", "forbescentroamerica.com", "web", "https://forbescentroamerica.com/",
           selectores=_WEB_TITULARES),
]


# Estados Unidos: búsquedas extra en español, además de la general de config/regiones.py.
BUSQUEDAS_EEUU = [
    '"Estados Unidos" "El Salvador" aranceles OR remesas OR deportaciones OR deportados OR TPS',
    '"Estados Unidos" "El Salvador" economía OR inversión OR acuerdo OR "Reserva Federal"',
    'Trump "El Salvador"',
    '"Estados Unidos" Centroamérica aranceles OR remesas OR migración OR economía',
]

REGION_BUSQUEDA = ('"El Salvador" OR Centroamérica OR Guatemala OR Honduras OR Nicaragua OR "Costa Rica" '
                   'OR Panamá OR "América Latina"')
# En las búsquedas de organismos, además del organismo el titular debe tocar a Centroamérica o a América Latina.
TITULAR_REGION = sorted({p for palabras in PAIS_KEYWORDS.values() for p in palabras} | {
    "centroamérica", "centroamericano", "centroamericana", "centroamericanos", "américa latina",
    "latinoamérica", "latinoamericano", "latinoamericana", "américa central", "triángulo norte"})


def _palabras_organismo(o: dict) -> list:
    return o.get("texto", []) + [s.lower() for s in o.get("siglas", [])]


def _url_google_news(consulta: str, pais: str, idioma: str = "es", gl: str = None) -> str:
    """Búsqueda en Google News; en español con región de Centroamérica, en otro idioma con el país `gl`."""
    q = quote_plus(f"{consulta} when:1d")
    if idioma != "es":
        hl = {"en": "en-US", "pt": "pt-BR"}.get(idioma, idioma)
        ceid_idioma = {"pt": "pt-419"}.get(idioma, idioma)
        return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{ceid_idioma}"
    gl = pais if pais in ("SV", "GT", "HN", "NI", "CR", "PA") else "SV"
    return f"https://news.google.com/rss/search?q={q}&hl=es-419&gl={gl}&ceid={gl}:es-419"


def consultas_google_news() -> list:
    """Una búsqueda por medio (site:dominio) y una por personaje y por partido, filtradas a medios conocidos.

    El parámetro gl de Google News no limita los medios al país, por eso se usa site:.
    """
    consultas = [
        {
            "nombre": f"Google News · {f['nombre']}", "pais": f["pais"], "tipo": "google_news",
            "activa": True, "medio": f["nombre"], "url": _url_google_news(f"site:{f['dominio']}", f["pais"]),
        }
        for f in FUENTES
    ]
    # Con varios site: entre paréntesis Google ignora el nombre; por eso se busca solo el nombre
    # y se descartan localmente los medios que no están en FUENTES.
    for nombre in PERSONAJES:
        consultas.append({
            "nombre": f"Google News · Personaje · {nombre}", "pais": "SV", "tipo": "google_news",
            "activa": True, "solo_medios_conocidos": True, "url": _url_google_news(f'"{nombre}"', "SV"),
        })
    for nombre, p in PARTIDOS.items():
        consultas.append({
            "nombre": f"Google News · Partido · {nombre}", "pais": "SV", "tipo": "google_news",
            "activa": True, "solo_medios_conocidos": True, "url": _url_google_news(p["busqueda"], "SV"),
        })
    # Regiones fuera de Centroamérica: el titular debe nombrar la región Y a El Salvador/Centroamérica.
    for codigo, r in REGIONES.items():
        busquedas = [f'"El Salvador" ({r["busqueda_es"]})'] + (BUSQUEDAS_EEUU if codigo == "US" else [])
        for i, busqueda in enumerate(busquedas, 1):
            consultas.append({
                "nombre": f"Google News · {r['nombre']} {i}", "pais": codigo, "tipo": "google_news",
                "activa": True, "titular": [r["es"], SV_ES], "url": _url_google_news(busqueda, codigo),
            })
        for idioma, gl, busqueda, palabras in r["extranjero"]:
            consultas.append({
                "nombre": f"Google News · {r['nombre']} ({idioma})", "pais": codigo, "tipo": "google_news",
                "activa": True, "idioma": idioma, "titular": [palabras, SV_POR_IDIOMA[idioma]],
                "url": _url_google_news(busqueda, codigo, idioma, gl),
            })
    # Organismos: el país de cada nota sale del texto, como en los medios regionales.
    for nombre, o in ORGANISMOS.items():
        consultas.append({
            "nombre": f"Google News · Organismo · {nombre}", "pais": "REG", "tipo": "google_news",
            "activa": True, "titular": [_palabras_organismo(o), TITULAR_REGION],
            "url": _url_google_news(f'({o["busqueda"]}) ({REGION_BUSQUEDA})', "SV"),
        })
    return consultas


def fuente_por_dominio(url: str):
    """Medio configurado cuyo dominio coincide con la URL, o None."""
    host = urlparse(url or "").netloc.lower()
    for f in FUENTES:
        if host == f["dominio"] or host.endswith("." + f["dominio"]):
            return f
    return None
