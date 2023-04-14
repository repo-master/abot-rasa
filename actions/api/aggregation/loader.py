
from .. import Client
from typing import Optional, Dict, Any


async def fetch_sensor_data(requested_sensor_id: Optional[str] = None,
                            requested_sensor_type: Optional[str] = None) -> Dict[str, Any]:
    async with Client() as client:
        params = {}
        if requested_sensor_id is not None:
            params.update({'sensor_id': requested_sensor_id})
        elif requested_sensor_type is not None:
            params.update({
                'sensor_type': requested_sensor_type,
                'result_type': 'best_match',
                'sort_by': 'user_geo'
            })
        response = await client.get("/data/sensor", params=params)
        return response.json()
