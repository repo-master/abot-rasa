
from httpx import AsyncClient
from httpx import HTTPStatusError

from .config import BACKEND_ENDPOINT_BASE


def Client(**kwargs) -> AsyncClient:
    return AsyncClient(base_url=BACKEND_ENDPOINT_BASE, timeout=60.0, **kwargs)
