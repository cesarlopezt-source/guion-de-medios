from unittest.mock import patch, MagicMock
import requests
from link_checker import check_url, check_urls


def test_check_url_returns_true_for_200():
    with patch("link_checker.requests.head") as mock_head:
        mock_head.return_value = MagicMock(status_code=200)
        assert check_url("http://ok.com") is True


def test_check_url_returns_false_for_404():
    with patch("link_checker.requests.head") as mock_head:
        mock_head.return_value = MagicMock(status_code=404)
        assert check_url("http://missing.com") is False


def test_check_url_returns_false_on_exception():
    with patch("link_checker.requests.head", side_effect=requests.RequestException("timeout")):
        assert check_url("http://timeout.com") is False


def test_check_urls_returns_map_for_each_url():
    with patch("link_checker.check_url", side_effect=lambda u, timeout=5.0: u == "http://ok.com"):
        result = check_urls(["http://ok.com", "http://bad.com"])
    assert result == {"http://ok.com": True, "http://bad.com": False}


def test_check_urls_deduplicates_input():
    calls = []

    def fake_check(u, timeout=5.0):
        calls.append(u)
        return True

    with patch("link_checker.check_url", side_effect=fake_check):
        check_urls(["http://x.com", "http://x.com"])
    assert calls == ["http://x.com"]


def test_check_urls_empty_list_returns_empty_dict():
    assert check_urls([]) == {}
