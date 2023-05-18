
'''
async def fetch_sensor_report(
        requested_sensor_id: int,
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

async def fetch_sensor_interactive_report(
        requested_sensor_id: int,
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
