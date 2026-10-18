from datetime import datetime, timedelta, timezone

from noticias import construir_noticias, filtrar, ordenar

AHORA = datetime.now(timezone.utc)


def mk(titulo, pais, fuente="LPG", temas=None, personajes=None, horas=1, url=None, resumen=""):
    return {"titulo": titulo, "resumen": resumen, "url": url or f"https://x/{titulo}/{fuente}/{pais}",
            "fuente": fuente, "pais": pais, "publicado": AHORA - timedelta(hours=horas), "via": "rss",
            "temas": temas or ["Economía"], "personajes": personajes or [], "menciona_sv": False}


def nt(pais, temas, personajes, puntaje=50.0, publicado="2026-10-05T12:00:00+00:00"):
    return {"titulo": "t", "pais": pais, "temas": temas, "personajes": personajes,
            "puntaje": puntaje, "publicado": publicado}


def test_no_agrupa_entre_paises():
    a = [mk("Sube el precio del café", "SV"), mk("Sube el precio del café", "GT")]
    assert len(construir_noticias(a)) == 2


def test_agrupa_mismo_pais_y_cuenta_fuentes():
    a = [mk("Remesas crecen 5% en septiembre", "SV", fuente="LPG"),
         mk("Remesas crecen 5% en septiembre 2026", "SV", fuente="EDH", resumen="más largo")]
    n = construir_noticias(a)
    assert len(n) == 1 and n[0]["n_fuentes"] == 2
    assert n[0]["titulo"] == "Remesas crecen 5% en septiembre 2026" and n[0]["resumen"] == "más largo"
    assert {f["nombre"] for f in n[0]["fuentes"]} == {"LPG", "EDH"}


def test_union_de_temas_sin_otras():
    a = [mk("X igual", "SV", temas=["Otras"]), mk("X igual!", "SV", temas=["Mujeres"], fuente="EDH")]
    assert construir_noticias(a)[0]["temas"] == ["Mujeres"]


def test_union_temas_y_personajes_en_orden_de_config():
    a = [mk("Mismo titular aquí", "SV", temas=["Política"], personajes=["Ernesto Castro"]),
         mk("Mismo titular aquí.", "SV", temas=["Economía"], personajes=["Nayib Bukele"], fuente="EDH")]
    n = construir_noticias(a)[0]
    assert n["temas"] == ["Economía", "Política"]
    assert n["personajes"] == ["Nayib Bukele", "Ernesto Castro"]


def test_estrellas_relativas_y_publicado_iso():
    a = [mk("Uno solo", "SV", horas=48), mk("Dos fuentes", "SV"), mk("Dos fuentes", "SV", fuente="EDH")]
    n = {x["titulo"]: x for x in construir_noticias(a)}
    assert n["Dos fuentes"]["estrellas"] == 5 and n["Uno solo"]["estrellas"] < 5
    datetime.fromisoformat(n["Uno solo"]["publicado"])


def test_construir_vacio():
    assert construir_noticias([]) == []


def test_filtro_personajes_vacio_no_filtra():
    ns = [nt("SV", ["Economía"], []), nt("SV", ["Economía"], ["Nayib Bukele"])]
    assert len(filtrar(ns, {"SV"}, {"Economía"}, set())) == 2
    assert len(filtrar(ns, {"SV"}, {"Economía"}, {"Nayib Bukele"})) == 1


def test_filtro_pais_y_tema():
    ns = [nt("SV", ["Deportes"], []), nt("GT", ["Economía"], []), nt("SV", ["Economía", "Mujeres"], [])]
    assert len(filtrar(ns, {"SV"}, {"Mujeres", "Política"}, set())) == 1


def test_ordenar_importancia():
    ns = [nt("SV", [], [], 10), nt("SV", [], [], 90), nt("SV", [], [], 50)]
    assert [n["puntaje"] for n in ordenar(ns, "importancia")] == [90, 50, 10]


def test_ordenar_recientes():
    ns = [nt("SV", [], [], 90, "2026-10-01T00:00:00+00:00"), nt("SV", [], [], 10, "2026-10-09T00:00:00+00:00")]
    assert [n["puntaje"] for n in ordenar(ns, "recientes")] == [10, 90]


def test_primera_fuente_es_el_articulo_mas_antiguo():
    # La pantalla usa pais|fuentes[0].url como clave de selección: no debe cambiar si llega un título más largo.
    a = [mk("Remesas crecen 5% en septiembre", "SV", fuente="LPG", horas=5, url="https://lpg/1"),
         mk("Remesas crecen 5% en septiembre 2026 según BCR", "SV", fuente="EDH", horas=1, url="https://edh/2")]
    n = construir_noticias(a)[0]
    assert n["fuentes"][0]["url"] == "https://lpg/1"
    assert n["titulo"].endswith("según BCR")


def test_filtro_partidos_aparte_de_personajes():
    ns = [nt("SV", ["Política"], ["Nayib Bukele"]), nt("SV", ["Política"], ["Nayib Bukele", "Nuevas Ideas"]),
          nt("SV", ["Política"], ["ARENA"])]
    assert len(filtrar(ns, {"SV"}, {"Política"}, set(), {"Nuevas Ideas", "ARENA"})) == 2
    assert len(filtrar(ns, {"SV"}, {"Política"}, {"Nayib Bukele"}, {"Nuevas Ideas"})) == 1
    assert len(filtrar(ns, {"SV"}, {"Política"}, set(), set())) == 3


def test_filtro_ambito():
    sv, gt, gt_sv = nt("SV", ["Economía"], []), nt("GT", ["Economía"], []), nt("GT", ["Economía"], [])
    gt_sv["menciona_sv"] = True
    ns = [sv, gt, gt_sv]
    todos = {"SV", "GT"}
    assert filtrar(ns, todos, {"Economía"}, set(), set(), {"Nacionales"}) == [sv, gt_sv]
    assert filtrar(ns, todos, {"Economía"}, set(), set(), {"Internacionales"}) == [gt, gt_sv]
    assert len(filtrar(ns, todos, {"Economía"}, set(), set(), set())) == 3


def test_estados_unidos_incluye_notas_de_su_relacion_con_la_region():
    tps = {**nt("SV", ["Economía"], []), "titulo": "Incertidumbre del TPS frena trámites de salvadoreños"}
    solo_sv = {**nt("SV", ["Economía"], []), "titulo": "Remesas crecen en El Salvador"}
    assert filtrar([tps, solo_sv], {"US"}, {"Economía"}, set()) == [tps]
    assert len(filtrar([tps, solo_sv], {"SV"}, {"Economía"}, set())) == 2
