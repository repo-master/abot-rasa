
from httpx import AsyncClient

from .config import BACKEND_ENDPOINT_BASE


def Client(**kwargs) -> AsyncClient:
    return AsyncClient(base_url=BACKEND_ENDPOINT_BASE, **kwargs)
