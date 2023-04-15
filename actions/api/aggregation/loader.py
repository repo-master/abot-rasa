
from .. import Client
from typing import Optional, Dict, Any


async def fetch_sensor_data(requested_sensor_id: str) -> Dict[str, Any]:
    async with Client() as client:
        params = {}

        params.update({'sensor_id': requested_sensor_id})
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


async def determine_user_request_sensor_id(sensor_type=None, sensor_name=None, location=None):
    print(f"looking into sensor master to find {sensor_type} sensor in {location}")
    if sensor_type == 'temperature':
        sensor_id = '1'
    elif sensor_type == 'humidity':
        sensor_id = '2'
    else:
        sensor_id = None
    print("sensor_id is : ", sensor_id)

    return sensor_id

