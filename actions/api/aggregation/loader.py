
from .. import Client
from .schema import SensorDataResponse
from typing import Optional
from datetime import datetime , timedelta

import json

async def fetch_sensor_data(requested_sensor_id: int, 
                      timestamp_from: Optional[datetime] = None,
                      timestamp_to: Optional[datetime] = None) -> SensorDataResponse:
    async with Client() as client:
        params = {}

        params.update({'sensor_id': requested_sensor_id, 'timestamp_from': timestamp_from.isoformat(), 'timestamp_to': timestamp_to.isoformat()})


        # This is the parameters that should be passed to guess sensor id from any known items (type, name, alias, location, etc.)
        # This will go into `user_guess_sensor_id`
        '''elif requested_sensor_type is not None:
            params.update({
                'sensor_type': requested_sensor_type,
                'result_type': 'best_match',
                'sort_by': 'user_geo'
            })
        '''
        response = await client.get("/data/sensor", params=params)
        return response.json()


async def determine_user_request_sensor_id(sensor_type=None, sensor_name=None, location=None) -> Optional[int]:
    async with Client() as client:
        params = {}
        params.update({'sensor_type': sensor_type,  'location': location})

        response = await client.get("/query/sensor_id", params=params)
        return response.json()['sensor_id']
        




