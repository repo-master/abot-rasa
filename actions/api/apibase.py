
from httpx import AsyncClient

from .config import API_BASE


def Client(**kwargs) -> AsyncClient:
    return AsyncClient(base_url=API_BASE, **kwargs)
