
from httpx import AsyncClient, ConnectError, HTTPStatusError

from .httpx_patches import monkeypatch_httpx
from .config import BACKEND_ENDPOINT_BASE

# Monkeypatch httpx to fix json encoder
monkeypatch_httpx()


def Client(**kwargs) -> AsyncClient:
    return AsyncClient(base_url=BACKEND_ENDPOINT_BASE, timeout=60.0, **kwargs)
