import pytest

from core.linkparse import parse_target


@pytest.mark.parametrize("text,host,port,path,scheme", [
    ("3000", "127.0.0.1", 3000, "", "http"),
    (":3000", "127.0.0.1", 3000, "", "http"),
    ("localhost:3000/x", "127.0.0.1", 3000, "/x", "http"),
    ("http://localhost:8080/app", "127.0.0.1", 8080, "/app", "http"),
    ("https://localhost:8443", "127.0.0.1", 8443, "", "https"),
    ("http://192.168.1.1", "192.168.1.1", 80, "", "http"),
    ("https://example.org", "example.org", 443, "", "https"),
    ("192.168.1.1:8080/", "192.168.1.1", 8080, "/", "http"),
])
def test_parse_ok(text, host, port, path, scheme):
    t = parse_target(text)
    assert (t.host, t.port, t.path, t.scheme) == (host, port, path, scheme)


@pytest.mark.parametrize("text", ["", "   ", "ftp://x", "http://h:99999", "http://h:0"])
def test_parse_errors(text):
    with pytest.raises(ValueError):
        parse_target(text)


def test_url_uses_local_port():
    assert parse_target("localhost:3000/a?b=1").url(5555) == "http://127.0.0.1:5555/a?b=1"
