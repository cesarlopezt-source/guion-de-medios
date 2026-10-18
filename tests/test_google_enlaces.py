import json

from collectors import google_enlaces

URL = "https://news.google.com/rss/articles/CBMiABC?oc=5"


class _Resp:
    def __init__(self, text, status_code=200):
        self.text, self.status_code = text, status_code


class _Sesion:
    def __init__(self, pagina, respuesta):
        self.pagina, self.respuesta, self.posts = pagina, respuesta, []

    def get(self, url, **kw):
        assert url == "https://news.google.com/articles/CBMiABC"
        return _Resp(self.pagina)

    def post(self, url, data, **kw):
        self.posts.append(data)
        return _Resp(self.respuesta)


PAGINA = '<c-wiz><div data-n-a-sg="FIRMA" data-n-a-ts="1760000000"></div></c-wiz>'


def _respuesta(real):
    return ")]}'\n\n" + json.dumps([["wrb.fr", "Fbv4je", json.dumps(["garturlres", real, 1])]])


def test_es_de_google():
    assert google_enlaces.es_de_google(URL)
    assert not google_enlaces.es_de_google("https://www.elsalvador.com/nota")


def test_enlace_real(monkeypatch):
    monkeypatch.undo()  # quita el bloqueo de conftest
    monkeypatch.setattr(google_enlaces, "INTERVALO_S", 0)
    monkeypatch.setattr(google_enlaces, "_pausa_hasta", 0.0)
    sesion = _Sesion(PAGINA, _respuesta("https://www.elsalvador.com/nota-1"))
    assert google_enlaces.enlace_real(URL, sesion) == "https://www.elsalvador.com/nota-1"
    assert "FIRMA" in sesion.posts[0] and "1760000000" in sesion.posts[0]


def test_enlace_real_sin_firma_o_esquema_raro(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(google_enlaces, "INTERVALO_S", 0)
    assert google_enlaces.enlace_real(URL, _Sesion("<html></html>", "")) == ""
    assert google_enlaces.enlace_real(URL, _Sesion(PAGINA, _respuesta("javascript:alert(1)"))) == ""
    assert google_enlaces.enlace_real("https://otro.com/x", _Sesion(PAGINA, "")) == ""


def test_429_pausa_y_devuelve_none(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(google_enlaces, "INTERVALO_S", 0)
    monkeypatch.setattr(google_enlaces, "_pausa_hasta", 0.0)

    class _Bloqueada(_Sesion):
        def get(self, url, **kw):
            self.gets = getattr(self, "gets", 0) + 1
            return _Resp("", 429)
    s = _Bloqueada(PAGINA, "")
    assert google_enlaces.enlace_real(URL, s) is None and google_enlaces.en_pausa()
    assert google_enlaces.enlace_real(URL, s) is None and s.gets == 1  # en pausa ya no pide nada


def test_error_de_red_devuelve_none(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(google_enlaces, "INTERVALO_S", 0)
    monkeypatch.setattr(google_enlaces, "_pausa_hasta", 0.0)

    class _Caida(_Sesion):
        def get(self, url, **kw):
            raise ConnectionError("sin red")
    assert google_enlaces.enlace_real(URL, _Caida(PAGINA, "")) is None
