from unittest.mock import MagicMock, patch

import requests

from link_checker import check_url, check_urls


def resp(code):
    return MagicMock(status_code=code)


def test_200_activa_y_envia_user_agent():
    with patch("link_checker.requests.head", return_value=resp(200)) as head:
        assert check_url("http://ok.com") is True
        assert "Mozilla" in head.call_args.kwargs["headers"]["User-Agent"]


def test_404_y_410_inactiva():
    for code in (404, 410):
        with patch("link_checker.requests.head", return_value=resp(code)):
            assert check_url("http://x.com") is False


def test_head_405_reintenta_con_get():
    with patch("link_checker.requests.head", return_value=resp(405)), \
         patch("link_checker.requests.get", return_value=resp(200)) as get:
        assert check_url("http://x.com") is True
        assert get.called


def test_bloqueo_403_o_429_es_desconocido():
    with patch("link_checker.requests.head", return_value=resp(403)), \
         patch("link_checker.requests.get", return_value=resp(403)):
        assert check_url("http://x.com") is None


def test_error_de_red_inactiva():
    with patch("link_checker.requests.head", side_effect=requests.ConnectionError("x")):
        assert check_url("http://caida.com") is False


def test_check_urls_deduplica():
    with patch("link_checker.check_url", side_effect=lambda u: u.endswith("ok")) as c:
        assert check_urls(["a/ok", "a/ok", "b/no"]) == {"a/ok": True, "b/no": False}
        assert c.call_count == 2


def test_check_urls_vacio():
    assert check_urls([]) == {}
