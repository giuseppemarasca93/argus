import pytest

from argus.http import HttpClient


class FakeResponse:
    def __init__(self, body=b"feed", status=200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def getcode(self):
        return self.status

    def read(self):
        return self.body


def test_http_client_sets_user_agent_and_timeout():
    received = {}

    def opener(request, timeout):
        received["user_agent"] = request.get_header("User-agent")
        received["timeout"] = timeout
        return FakeResponse(b"rss")

    assert HttpClient(timeout=3, opener=opener).fetch("https://example.com/feed") == b"rss"
    assert received == {"user_agent": "Argus/0.1", "timeout": 3}


def test_http_client_rejects_invalid_status():
    client = HttpClient(opener=lambda request, timeout: FakeResponse(status=503))

    with pytest.raises(RuntimeError, match="503"):
        client.fetch("https://example.com/feed")
