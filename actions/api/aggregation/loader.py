
import json
from datetime import datetime
from typing import Optional

from .. import Client
from .schema import SensorDataResponse, SensorMetadata


async def fetch_sensor_data(requested_sensor_id: int,
                            timestamp_from: Optional[datetime] = None,
                            timestamp_to: Optional[datetime] = None) -> SensorDataResponse:
    async with Client() as client:
        params = {}

        params.update({
            'sensor_id': requested_sensor_id,
            'timestamp_from': timestamp_from.isoformat(),
            'timestamp_to': timestamp_to.isoformat()
        })

        response = await client.get("/data/sensor", params=params)
        response.raise_for_status()
        return response.json()


async def determine_user_request_sensor(sensor_type=None, sensor_name=None, location=None) -> Optional[SensorMetadata]:
    async with Client() as client:
        params = {}
        params.update({
            'sensor_type': sensor_type,
            'sensor_name': sensor_name,
            'location': location
        })

        response = await client.get("/query/sensor_id", params=params)
        response.raise_for_status()
        try:
            data: dict = response.json()
            sensor: Optional[SensorMetadata] = data.get('sensor')
            return sensor
        except json.decoder.JSONDecodeError:
            # TODO: Utter something, since the backend HAS to send JSON.
            # We reached here meaning data we got is not JSON
            pass
