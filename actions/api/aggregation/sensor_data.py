
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .loader import fetch_sensor_data
from .schema import AggregationMethod, SensorDataResponse, SensorMetadata


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


def user_to_sensor_type(name: Optional[str]) -> Optional[str]:
    name = name.lower() if name is not None else ''
    if name == 'temp' or name == 'temperature':
        return 'temp'
    elif name == 'humidity' or name == 'rh':
        return 'rh'
    elif name == 'em' or name == 'energy' or name == 'power':
        return 'em'


def user_to_aggregation_type(name: Optional[str]) -> AggregationMethod:
    aggregation = AggregationMethod.CURRENT
    if name is not None:
        m = name.lower()
        if m == "minimum":
            aggregation = AggregationMethod.MINIMUM
        elif m == "maximum":
            aggregation = AggregationMethod.MAXIMUM
        elif m == "average":
            aggregation = AggregationMethod.AVERAGE
        elif m == 'summary':
            aggregation = AggregationMethod.SUMMARY
    return aggregation
