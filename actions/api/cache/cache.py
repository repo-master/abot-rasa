
import logging
from typing import Any, Awaitable, Callable, Dict

import pandas as pd

from .. import statapi

LOGGER = logging.getLogger(__name__)


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

    async def invalidate(self, events: list, force: bool = False):
        if force or self._content == self.NOT_SET:
            await self._load(events, **self._loader_params)
        return self

    async def _load(self, events: list, **params):
        if self._loader:
            LOGGER.debug("Updating cache %s" % str(self))
            self._content = await self._loader(**params)
            events.append({
                "event": "cache_update",
                "timestamp": None,
                "cache": str(self)
            })


class PandasDataCache(Cache):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.df: pd.DataFrame = None
        self.metadata: dict = None
        self.insights: list = []

    async def _load(self, events: list, **params):
        await super()._load(events, **params)
        if self._content != self.NOT_SET:
            self.df: pd.DataFrame = self._content['data']
            self.metadata: dict = self._content['metadata']
            self.insights: list = []

            if not self.df.empty:
                outliers_result = await statapi.outliers(self.df)
                # TODO: Add more analysis functions

                # TODO: Move this to insights
                for _, outlier_ser in outliers_result.iterrows():
                    self.insights.append({
                        "type": "outlier",
                        "data_point": outlier_ser
                    })

            # Count
            insight_type_counts: Dict[str, int] = {}
            for detected_insight in self.insights:
                if detected_insight['type'] not in insight_type_counts.keys():
                    insight_type_counts[detected_insight['type']] = 0
                insight_type_counts[detected_insight['type']] += 1

            events.append({
                "event": "data_analysis_done",
                "timestamp": None,
                "insights": self.insights,
                "counts": insight_type_counts
            })


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
