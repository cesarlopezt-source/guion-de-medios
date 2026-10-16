from classifier import clasificar


def art(t, r="", pais="SV"):
    return {"titulo": t, "resumen": r, "pais": pais}


def test_multitema():
    a = clasificar(art("Programa de créditos para mujeres emprendedoras", "inversión de BANDESAL"))
    assert {"Mujeres", "Inversión"} <= set(a["temas"])


def test_sin_tema_es_otras():
    assert clasificar(art("Hoy amaneció nublado sin más"))["temas"] == ["Otras"]


def test_tildes_y_mayusculas():
    assert "Economía" in clasificar(art("LA ECONOMIA crece"))["temas"]


def test_personaje_por_variante():
    assert clasificar(art("Bukele inaugura obra"))["personajes"] == ["Nayib Bukele"]


def test_menciona_sv_solo_fuera_de_sv():
    assert clasificar(art("Acuerdo con El Salvador", pais="GT"))["menciona_sv"] is True
    assert clasificar(art("Acuerdo con El Salvador", pais="SV"))["menciona_sv"] is False


def test_regional_asigna_pais_mencionado():
    assert clasificar(art("Exportaciones de Guatemala crecen", pais="REG"))["pais"] == "GT"
    assert clasificar(art("Exportaciones del istmo crecen", pais="REG"))["pais"] == "REG"


def test_temas_en_orden_de_config():
    assert clasificar(art("Gobierno y economía"))["temas"] == ["Economía", "Política"]


def test_no_muta_entrada():
    a = art("Bukele")
    clasificar(a)
    assert "temas" not in a


def test_palabra_completa_no_subcadena():
    assert "Deportes" not in clasificar(art("Golpe a la música local"))["temas"]


def test_partidos_por_nombre_y_siglas():
    a = clasificar(art("Diputados de Nuevas Ideas y ARENA discuten presupuesto", "El FMLN y el PCN votaron en contra"))
    assert a["personajes"] == ["Nuevas Ideas", "ARENA", "FMLN", "PCN"]


def test_partido_vamos_y_nuestro_tiempo_solo_como_partido():
    assert clasificar(art("La diputada de Vamos pidió cuentas"))["personajes"] == ["Vamos"]
    assert clasificar(art("Vamos a ver qué pasa con la arena del río"))["personajes"] == []
    assert clasificar(art("El partido Nuestro Tiempo inscribe candidatos"))["personajes"] == ["Nuestro Tiempo"]


def test_siglas_no_se_confunden_con_titulares_en_mayusculas():
    assert clasificar(art("SELECTA GANA EN CASA"))["personajes"] == []
    assert clasificar(art("La arena de la playa"))["personajes"] == []
