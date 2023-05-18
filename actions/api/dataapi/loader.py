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

async def cached_loader(cache: CacheHolder = DatasetCache, loader=None, **params) -> Cache:
    cache['test'] = {
        'input': params,
        'loader': loader,
        'content': None
    }
    cache['test']['content'] = await loader(**params)

async def get_loaded_data(tracker: Tracker, cache: CacheHolder = DatasetCache):
    data_source: str = tracker.get_slot("data_source")
    return cache.get(data_source)
