
from .. import Client
from .schema import SensorDataResponse

from typing import Optional
from datetime import datetime

async def get_report_generate_preview(requested_sensor_id: int,
                            timestamp_from: Optional[datetime] = None,
                            timestamp_to: Optional[datetime] = None) -> SensorDataResponse:
    async with Client() as client:
        params = {}

        params.update({
            'sensor_id': requested_sensor_id,
            'timestamp_from': timestamp_from.isoformat(),
            'timestamp_to': timestamp_to.isoformat()
        })
            # TO DO timestamp error need to fix


        response = await client.get("/data/report", params=params)
        response.raise_for_status()

        return response.json()
