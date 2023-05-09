'''Fetch data from data source'''

import json
from datetime import datetime
from typing import List, Optional

from .. import Client
from .schemas import SensorDataResponse, SensorMetadata


async def fetch_sensor_data(requested_sensor_id: int,
                            timestamp_from: Optional[datetime] = None,
                            timestamp_to: Optional[datetime] = None) -> SensorDataResponse:
    async with Client() as client:
        params = {}

        params.update({
            'sensor_id': requested_sensor_id,
            'timestamp_from': timestamp_from,
            'timestamp_to': timestamp_to
        })

        response = await client.get("/genesis/data/sensor", params=params)
        response.raise_for_status()
        return response.json()


async def find_sensor(sensor_type=None, sensor_name=None, location=None) -> Optional[SensorMetadata]:
    async with Client() as client:
        params = {}
        params.update({
            'sensor_type': sensor_type,
            'sensor_name': sensor_name,
            'location': location
        })

        response = await client.get("/genesis/query/sensor/find", params=params)
        response.raise_for_status()
        try:
            data: dict = response.json()
            return data
        except json.decoder.JSONDecodeError:
            # TODO: Utter something, since the backend HAS to send JSON.
            # We reached here meaning data we got is not JSON
            pass

async def fetch_sensor_list() -> List[SensorMetadata]:
    async with Client() as client:
        response = await client.get("/genesis/query/sensor/list")
        response.raise_for_status()
        return response.json()

async def fetch_sensor_report(requested_sensor_id: int,
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
