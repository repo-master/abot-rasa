
from typing import Awaitable


class Cache:
    NOT_SET = object()

    def __init__(self, name: str, loader: Awaitable, **params):
        self._name = name
        self._loader = loader
        self._loader_params = params
        self._content = self.NOT_SET

    def __hash__(self):
        return hash(self._name)

    def __str__(self) -> str:
        return "<%s %s>" % (str(type(self)), self._name)

    async def invalidate(self, force: bool = False):
        # Check if cache hit or miss
        if force or self._content == self.NOT_SET:
            # Cache miss
            self._content = await self._loader(**self._loader_params)
        return self._content


class PandasData(Cache):
    def __init__(self, df):
        super().__init__()
        self.df = df


class CacheHolder(dict):
    async def __call__(self):
        pass


GlobalCache = CacheHolder()
