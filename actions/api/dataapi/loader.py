'''Fetch data from data source'''

from rasa_sdk import Tracker

from .. import FulfillmentClient
from ..cache.cache import Cache, PandasDataCache, CacheHolder
from .schemas import DataLoaderRequest

from typing import Optional


DatasetCache = CacheHolder()


async def request_json(req: DataLoaderRequest):
    async with FulfillmentClient() as client:
        response = await client.request(**req)
        response.raise_for_status()
        return response.json()

# TODO: User ID segregation


async def cached_loader(tracker: Tracker, datasource_name: str, cache: CacheHolder = DatasetCache, loader=None, **params) -> Cache:
    cache[datasource_name] = PandasDataCache(
        name=datasource_name,
        loader=loader,
        **params
    )

def get_cache(dataset_name: str, cache: CacheHolder = DatasetCache) -> Optional[Cache]:
    return cache.get(dataset_name)

async def get_loaded_data(tracker: Tracker, events: list, cache: CacheHolder = DatasetCache) -> Optional[Cache]:
    data_source: str = tracker.get_slot("data_source")
    c = cache.get(data_source)
    if isinstance(c, Cache):
        return await c.invalidate(events)
