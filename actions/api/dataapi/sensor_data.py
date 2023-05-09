
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .loader import (fetch_sensor_data, fetch_sensor_list, fetch_sensor_report,
                     find_sensor)
from .schemas import SensorDataResponse, SensorMetadata


async def get_sensor_data(requested_sensor_id: int,
                          timestamp_from: Optional[datetime] = None,
                          timestamp_to: Optional[datetime] = None) -> Optional[Tuple[pd.DataFrame, SensorMetadata]]:
    sensor_data: SensorDataResponse = await fetch_sensor_data(requested_sensor_id, timestamp_from, timestamp_to)

    if not ('data' in sensor_data and 'metadata' in sensor_data):
        return

    metadata: SensorMetadata = sensor_data.get('metadata', {})
    values: List[Dict] = sensor_data.get('data', [])

    # Create a DataFrame from the above data
    data = pd.DataFrame(values, index=None)

    # Remove rows with NaN in them
    data.dropna(inplace=True, axis=1)

    if len(data) > 0:
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.sort_values('timestamp', ascending=False, inplace=True)
        # We get a dictionary result in the 'value' column. We need to 'explode' it to separate columns.
        data_value_series = data['value'].apply(pd.Series)
        # Concatenate the data value columns to original df, remove the 'value' column from original
        data = pd.concat([data.drop(['value'], axis=1), data_value_series], axis=1)

    return data, metadata

async def query_sensor_list() -> List[SensorMetadata]:
    return await fetch_sensor_list()

async def determine_user_request_sensor(sensor_type=None, sensor_name=None, location=None) -> Optional[SensorMetadata]:
    return await find_sensor(sensor_type, sensor_name, location)

async def get_report_generate_preview(requested_sensor_id: int,
                                      timestamp_from: Optional[datetime] = None,
                                      timestamp_to: Optional[datetime] = None) -> SensorDataResponse:
    return await fetch_sensor_report(requested_sensor_id, timestamp_from, timestamp_to)

def user_to_sensor_type(name: Optional[str]) -> Optional[str]:
    name = name.lower() if name is not None else ''
    if name == 'temp' or name == 'temperature':
        return 'temp'
    elif name == 'humidity' or name == 'rh':
        return 'rh'
    elif name == 'em' or name == 'energy' or name == 'power':
        return 'em'

__all__ = [
    'get_sensor_data',
    'query_sensor_list',
    'determine_user_request_sensor',
    'get_report_generate_preview',
    'user_to_sensor_type'
]
