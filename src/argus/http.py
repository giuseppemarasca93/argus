from __future__ import annotations

from collections.abc import Callable
from urllib.request import Request, urlopen


class HttpClient:
    def __init__(
        self,
        timeout: float = 15,
        user_agent: str = "Argus/0.1",
        opener: Callable = urlopen,
    ) -> None:
        if timeout <= 0:
            raise ValueError("Il timeout HTTP deve essere maggiore di zero")
        self.timeout = timeout
        self.user_agent = user_agent
        self.opener = opener

    def fetch(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with self.opener(request, timeout=self.timeout) as response:
            status = response.getcode()
            if status is not None and not 200 <= status < 300:
                raise RuntimeError(f"Risposta HTTP non valida: {status}")
            return response.read()

