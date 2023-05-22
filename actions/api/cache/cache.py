
import pandas as pd

from typing import Any, Callable, Awaitable


class Cache:
    NOT_SET = object()

    def __init__(self, name: str, loader: Callable[[Any], Awaitable], **params):
        self._name = name
        self._loader = loader
        self._loader_params = params
        self._content = self.NOT_SET

    @property
    def content(self):
        return self._content

    def __hash__(self):
        return hash(self._name)

    def __str__(self) -> str:
        return "<%s %s>" % (self.__class__.__name__, self._name)

    async def invalidate(self, force: bool = False):
        if force or self._content == self.NOT_SET:
            await self._load(**self._loader_params)
        return self

    async def _load(self, **params):
        if self._loader:
            print("Updating cache %s" % str(self))
            self._content = await self._loader(**params)

class PandasDataCache(Cache):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.df: pd.DataFrame = None
        self.metadata: dict = None
    async def _load(self, **params):
        await super()._load(**params)
        if self._content != self.NOT_SET:
            self.df = self._content['data']
            self.metadata = self._content['metadata']


class CacheHolder(dict):
    async def __call__(self):
        pass


GlobalCache = CacheHolder()

__all__ = [
    'CacheHolder',
    'Cache',
    'PandasDataCache',
    'GlobalCache'
]
