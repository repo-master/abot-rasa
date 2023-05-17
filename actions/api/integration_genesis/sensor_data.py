
from datetime import datetime
from typing import List, Optional

from ..client import Client
from .schemas import SensorDataResponse, SensorMetadata, UnitMetadata
from ..dataapi.schemas import DataLoaderRequest


def sensor_name_coalesce(meta: SensorMetadata) -> str:
    return meta.get('sensor_alias') or \
        meta.get('sensor_name') or \
        meta.get('sensor_urn')

def unit_name_coalesce(meta: UnitMetadata) -> str:
    return meta.get('unit_alias').split(',')[0] or \
        meta.get('unit_urn')

async def query_sensor_list() -> List[SensorMetadata]:
    return #await mkrequest_fetch_sensor_list()

async def determine_user_request_sensor(sensor_type=None, sensor_name=None, location=None) -> SensorMetadata:
    async with Client() as client:
        params = {
            'sensor_type': sensor_type,
            'sensor_name': sensor_name,
            'location': location
        }

        response = await client.get("/genesis/query/sensor/find", params=params)
        response.raise_for_status()
        return response.json()


async def get_report_generate_preview(requested_sensor_id: int,
                                      timestamp_from: Optional[datetime] = None,
                                      timestamp_to: Optional[datetime] = None) -> SensorDataResponse:
    return #await mkrequest_fetch_sensor_report(requested_sensor_id, timestamp_from, timestamp_to)

def user_to_sensor_type(name: Optional[str]) -> Optional[str]:
    name = name.lower() if name is not None else ''
    if name == 'temp' or name == 'temperature':
        return 'temp'
    elif name == 'humidity' or name == 'rh':
        return 'rh'
    elif name == 'em' or name == 'energy' or name == 'power':
        return 'em'


def mkrequest_fetch_sensor_data(metadata, fetch_range) -> DataLoaderRequest:
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

def mkrequest_find_sensor(sensor_type=None, sensor_name=None, location=None) -> Optional[SensorMetadata]:
    params = {
        'sensor_type': sensor_type,
        'sensor_name': sensor_name,
        'location': location
    }

    response = ("/genesis/query/sensor/find", params)
    '''response.raise_for_status()
    try:
        data: dict = response.json()
        return data
    except json.decoder.JSONDecodeError:
        # TODO: Utter something, since the backend HAS to send JSON.
        # We reached here meaning data we got is not JSON
        pass'''

'''
def mkrequest_fetch_sensor_list() -> List[SensorMetadata]:
    async with Client() as client:
        response = await client.get("/genesis/query/sensor/list")
        response.raise_for_status()
        return response.json()

def mkrequest_fetch_sensor_report(requested_sensor_id: int,
                              timestamp_from: Optional[datetime] = None,
                              timestamp_to: Optional[datetime] = None) -> SensorDataResponse:
    async with Client() as client:
        params = {}

        params.update({
            'sensor_id': requested_sensor_id,
            'timestamp_from': timestamp_from,
            'timestamp_to': timestamp_to
        })

        response = await client.get("/genesis/data/report", params=params)
        response.raise_for_status()

        return response.json()
'''

__all__ = [
    'query_sensor_list',
    'determine_user_request_sensor',
    'get_report_generate_preview',
    'user_to_sensor_type',
    'sensor_name_coalesce',
    'unit_name_coalesce'
]
