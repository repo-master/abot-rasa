
from .. import Client


async def get_report_generate_preview():
    async with Client() as client:
        params = {}

        params.update({
            'sensor_id': 1
        })

        response = await client.get("/data/report", params=params)
        return response.json()
