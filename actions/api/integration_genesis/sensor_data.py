
import json
import urllib.parse
from typing import List, Optional

from ..client import Client
from ..dataapi.schemas import DataLoaderRequest
from ..duckling import TimeRange
from .schemas import LocationMetadata, SensorMetadata


def sensor_name_coalesce(meta: SensorMetadata) -> str:
    return meta.get('sensor_alias') or \
        meta.get('sensor_name') or \
        meta.get('sensor_urn')


def location_name_coalesce(meta: LocationMetadata) -> str:
    return meta.get('unit_alias').split(',')[0] or \
        meta.get('unit_urn')


async def query_sensor_list() -> List[SensorMetadata]:
    async with Client() as client:
        response = await client.get("/genesis/query/sensor/list")
        response.raise_for_status()
        return response.json()

async def query_location_list() -> List[LocationMetadata]:
    async with Client() as client:
        response = await client.get("/genesis/query/unit/list")
        response.raise_for_status()
        return response.json()

async def determine_user_request_sensor(sensor_type=None, sensor_name=None, location=None) -> Optional[List[SensorMetadata]]:
    async with Client() as client:
        params = {
            'sensor_type': sensor_type,
            'location': location,
            'sensor_name': sensor_name
        }

        response = await client.get("/genesis/query/sensor/find", params=params)
        response.raise_for_status()

        try:
            return response.json()
        except json.decoder.JSONDecodeError:
            pass


async def sensor_query_metadata(sensor_id: int) -> Optional[SensorMetadata]:
    async with Client() as client:
        response = await client.get("/genesis/query/sensor", params={
            'sensor_id': sensor_id
        })
        try:
            response.raise_for_status()
            return response.json()
        except json.decoder.JSONDecodeError:
            pass


async def get_report_generate_preview(metadata: SensorMetadata, fetch_range: TimeRange):
    async with Client() as client:
        params = {}

        params.update({
            'sensor_id': metadata['sensor_id'],
            'timestamp_from': fetch_range["from"],
            'timestamp_to': fetch_range["to"],
            'preview_image': True,
            'plot_interactive': True
        })

        response = await client.get("/genesis/data/report", params=params)
        response.raise_for_status()

        return response.json()

def get_report_download_url(metadata: SensorMetadata, fetch_range: TimeRange, format: str = 'pdf') -> str:
    # Temporary
    query_params = urllib.parse.urlencode({
        'sensor_id': metadata['sensor_id'],
        'timestamp_from': fetch_range["from"],
        'timestamp_to': fetch_range["to"]
    })
    return f"/genesis/data/report/download/{format}?{query_params}"

def user_to_sensor_type(name: Optional[str]) -> Optional[str]:
    name = name.lower() if name is not None else ''
    if name == 'temp' or name == 'temperature':
        return 'temp'
    elif name == 'humidity' or name == 'rh':
        return 'rh'
    elif name == 'em' or name == 'energy' or name == 'power':
        return 'em'


def mkrequest_fetch_sensor_data(metadata: SensorMetadata, fetch_range: TimeRange) -> DataLoaderRequest:
    params = {
        'sensor_id': metadata["sensor_id"],
        'timestamp_from': fetch_range["from"],
        'timestamp_to': fetch_range["to"]
    }

    return DataLoaderRequest(
        method='get',
        url='/genesis/data/sensor',
        params=params
    )


__all__ = [
    'query_sensor_list',
    'query_location_list',
    'determine_user_request_sensor',
    'sensor_query_metadata',
    'get_report_generate_preview',
    'get_report_download_url',
    'user_to_sensor_type',
    'sensor_name_coalesce',
    'location_name_coalesce'
]
