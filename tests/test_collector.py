from argus.collector import collect
from argus.database import ArticleStore


FEED = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Test</title>
<item><title>Working article</title><link>https://example.com/a</link></item>
</channel></rss>"""


class FakeHttpClient:
    def fetch(self, url):
        if "broken" in url:
            raise TimeoutError("timed out")
        return FEED


def test_http_error_does_not_interrupt_other_sources(tmp_path):
    sources = [
        {"name": "Broken", "url": "https://broken.example/feed"},
        {"name": "Working", "url": "https://working.example/feed"},
    ]
    store = ArticleStore(tmp_path / "argus.db")

    result = collect(sources, store, FakeHttpClient())

    assert result.failed_sources == 1
    assert result.added == 1
    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1
