
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..dataapi.loader import request_json
from .schemas import SensorDataResponse, SensorMetadata
from .sensor_data import mkrequest_fetch_sensor_data


async def get_sensor_data(
        metadata,
        fetch_range) -> Optional[Tuple[pd.DataFrame, SensorMetadata]]:
    # await mkrequest_fetch_sensor_data(requested_sensor_id, timestamp_from, timestamp_to)
    sensor_data: SensorDataResponse = await request_json(mkrequest_fetch_sensor_data(metadata, fetch_range))

    if not ('data' in sensor_data and 'metadata' in sensor_data):
        return

    sensor_metadata: SensorMetadata = sensor_data.get('metadata', {})
    values: List[Dict] = sensor_data.get('data', [])

    # Create a DataFrame from the above data
    data = pd.DataFrame(values, index=None)

    # Remove rows with NaN in them
    data.dropna(inplace=True, axis=1)

    if len(data) > 0:
        data['timestamp'] = pd.to_datetime(data['timestamp'], format='ISO8601')
        data.sort_values('timestamp', ascending=False, inplace=True)
        # We get a dictionary result in the 'value' column. We need to 'explode' it to separate columns.
        data_value_series = data['value'].apply(pd.Series)
        # Concatenate the data value columns to original df, remove the 'value' column from original
        data = pd.concat([data.drop(['value'], axis=1), data_value_series], axis=1)

    return data, sensor_metadata

__all__ = [
    'get_sensor_data'
]
