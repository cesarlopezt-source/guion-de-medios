# Organismos internacionales: tienen su propio menú en el portal (como Partidos) y además búsquedas
# propias en Google News.
#   texto:    variantes sin tildes ni mayúsculas, palabra completa.
#   siglas:   en mayúsculas exactas; no cuentan dentro de un titular escrito todo en mayúsculas.
#   busqueda: consulta en Google News (se combina con El Salvador / la región).
ORGANISMOS = {
    "FMI": {"texto": ["fondo monetario internacional", "fondo monetario"], "siglas": ["FMI"],
            "busqueda": '"FMI" OR "Fondo Monetario Internacional"'},
    "BID": {"texto": ["banco interamericano de desarrollo", "grupo bid"], "siglas": ["BID"],
            "busqueda": '"BID" OR "Banco Interamericano de Desarrollo"'},
    "Banco Mundial": {"texto": ["banco mundial", "grupo banco mundial"], "busqueda": '"Banco Mundial"'},
    "ONU": {"texto": ["naciones unidas", "unicef", "pnud", "acnur", "unesco", "consejo de seguridad"],
            "siglas": ["ONU", "OIT", "OMS", "OPS", "FAO", "PMA", "OIM"],
            "busqueda": '"ONU" OR "Naciones Unidas"'},
    "BCIE": {"texto": ["banco centroamericano de integración económica"], "siglas": ["BCIE"],
             "busqueda": '"BCIE" OR "Banco Centroamericano de Integración Económica"'},
    "OEA": {"texto": ["organización de los estados americanos"], "siglas": ["OEA"],
            "busqueda": '"OEA" OR "Organización de los Estados Americanos"'},
    "CEPAL": {"texto": ["comisión económica para américa latina", "cepal"], "busqueda": '"CEPAL"'},
    "SICA": {"texto": ["sistema de la integración centroamericana"], "siglas": ["SICA"],
             "busqueda": '"SICA" OR "Sistema de la Integración Centroamericana"'},
    "Unión Europea": {"texto": ["unión europea", "comisión europea", "parlamento europeo"], "siglas": ["UE"],
                      "busqueda": '"Unión Europea" OR "Comisión Europea"'},
}
