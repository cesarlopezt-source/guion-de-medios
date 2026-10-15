from texto import normalizar, limpiar_html


def test_normalizar_quita_tildes_y_mayusculas():
    assert normalizar("Economía BUKELE Inversión") == "economia bukele inversion"


def test_normalizar_enie():
    assert normalizar("Año Peña") == "ano pena"


def test_limpiar_html():
    assert limpiar_html('<p>Hola&nbsp;<b>mundo</b></p><img src="x">') == "Hola mundo"


def test_limpiar_html_vacio():
    assert limpiar_html(None) == ""
