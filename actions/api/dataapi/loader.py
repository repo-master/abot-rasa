'''Fetch data from data source'''

from rasa_sdk import Tracker

from .. import Client
from ..cache.cache import Cache, CacheHolder
from .schemas import DataLoaderRequest

from typing import Type


DatasetCache = CacheHolder()


async def request_json(req: DataLoaderRequest):
    async with Client() as client:
        response = await client.request(**req)
        response.raise_for_status()
        return response.json()

# TODO: User ID segregation


async def cached_loader(dataset_name: str, cache: CacheHolder = DatasetCache, loader=None, **params) -> Cache:
    cache[dataset_name] = {
        'input': params,
        'loader': loader,
        'content': await loader(**params)
    }


def get_cache(dataset_name: str, cache: CacheHolder = DatasetCache):
    return cache.get(dataset_name)


async def get_loaded_data(tracker: Tracker, cache: CacheHolder = DatasetCache):
    data_source: str = tracker.get_slot("data_source")
    return cache.get(data_source)
