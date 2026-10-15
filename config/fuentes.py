from urllib.parse import quote_plus

from config.personajes import PERSONAJES


def _rss(nombre, pais, url):
    return {"nombre": nombre, "pais": pais, "tipo": "rss", "url": url, "activa": True}


FUENTES = [
    # El Salvador
    _rss("La Prensa Gráfica", "SV", "https://www.laprensagrafica.com/arc/outboundfeeds/rss/?outputType=xml"),
    _rss("El Diario de Hoy", "SV", "https://www.elsalvador.com/feed/"),
    _rss("Diario El Mundo", "SV", "https://diario.elmundo.sv/feed"),
    _rss("Diario Co Latino", "SV", "https://www.diariocolatino.com/feed/"),
    _rss("El Faro", "SV", "https://elfaro.net/rss"),
    _rss("Diario El Salvador", "SV", "https://diarioelsalvador.com/feed/"),
    _rss("La Página", "SV", "https://www.lapagina.com.sv/feed/"),
    _rss("Revista Factum", "SV", "https://www.revistafactum.com/feed/"),
    _rss("GatoEncerrado", "SV", "https://gatoencerrado.news/feed/"),
    # Guatemala
    _rss("Prensa Libre", "GT", "https://www.prensalibre.com/feed/"),
    _rss("Soy502", "GT", "https://www.soy502.com/rss"),
    _rss("República", "GT", "https://republica.gt/feed"),
    _rss("La Hora GT", "GT", "https://lahora.gt/feed/"),
    _rss("Plaza Pública", "GT", "https://www.plazapublica.com.gt/rss.xml"),
    _rss("Agencia Ocote", "GT", "https://www.agenciaocote.com/feed/"),
    # Honduras
    _rss("La Prensa HN", "HN", "https://www.laprensa.hn/rss"),
    _rss("El Heraldo", "HN", "https://www.elheraldo.hn/rss"),
    _rss("Proceso Digital", "HN", "https://proceso.hn/feed/"),
    _rss("La Tribuna", "HN", "https://www.latribuna.hn/feed/"),
    _rss("Criterio.hn", "HN", "https://criterio.hn/feed/"),
    _rss("Contracorriente", "HN", "https://contracorriente.red/feed/"),
    # Nicaragua
    _rss("La Prensa NI", "NI", "https://www.laprensani.com/feed/"),
    _rss("Confidencial", "NI", "https://confidencial.digital/feed/"),
    _rss("100% Noticias", "NI", "https://100noticias.com.ni/feed/"),
    _rss("Artículo 66", "NI", "https://www.articulo66.com/feed/"),
    _rss("Divergentes", "NI", "https://www.divergentes.com/feed/"),
    _rss("El 19 Digital", "NI", "https://www.el19digital.com/rss"),
    # Costa Rica
    _rss("La Nación", "CR", "https://www.nacion.com/arc/outboundfeeds/rss/?outputType=xml"),
    _rss("CRHoy", "CR", "https://www.crhoy.com/feed/"),
    _rss("El Financiero CR", "CR", "https://www.elfinancierocr.com/arc/outboundfeeds/rss/?outputType=xml"),
    _rss("Teletica", "CR", "https://www.teletica.com/rss"),
    _rss("Delfino", "CR", "https://delfino.cr/feed"),
    _rss("Semanario Universidad", "CR", "https://semanariouniversidad.com/feed/"),
    # Panamá
    _rss("La Prensa PA", "PA", "https://www.prensa.com/arc/outboundfeeds/rss/?outputType=xml"),
    _rss("La Estrella de Panamá", "PA", "https://www.laestrella.com.pa/rss"),
    _rss("Panamá América", "PA", "https://www.panamaamerica.com.pa/rss.xml"),
    _rss("TVN Noticias", "PA", "https://www.tvn-2.com/rss"),
    _rss("Telemetro", "PA", "https://www.telemetro.com/rss"),
    # Regionales
    _rss("Estrategia & Negocios", "REG", "https://www.estrategiaynegocios.net/rss"),
    _rss("Revista Summa", "REG", "https://revistasumma.com/feed/"),
    _rss("Forbes Centroamérica", "REG", "https://forbescentroamerica.com/feed"),
]

PAISES_GOOGLE_NEWS = ["SV", "GT", "HN", "NI", "CR", "PA"]

GRUPOS_GOOGLE_NEWS = {
    "Economía": "economía OR inversión OR remesas OR exportaciones",
    "Política": "política OR gobierno OR asamblea OR congreso",
    "Coyuntura": "FMI OR deuda OR presupuesto OR reforma",
    "Social": "mujeres OR inclusión OR género OR discapacidad",
}


def _url_google_news(consulta: str, pais: str) -> str:
    q = quote_plus(f"{consulta} when:1d")
    return f"https://news.google.com/rss/search?q={q}&hl=es-419&gl={pais}&ceid={pais}:es-419"


def consultas_google_news() -> list:
    consultas = []
    for pais in PAISES_GOOGLE_NEWS:
        for grupo, consulta in GRUPOS_GOOGLE_NEWS.items():
            consultas.append({
                "nombre": f"Google News · {pais} · {grupo}", "pais": pais, "tipo": "google_news",
                "activa": True, "url": _url_google_news(consulta, pais),
            })
    for nombre in PERSONAJES:
        consultas.append({
            "nombre": f"Google News · SV · {nombre}", "pais": "SV", "tipo": "google_news",
            "activa": True, "url": _url_google_news(f'"{nombre}"', "SV"),
        })
    return consultas
