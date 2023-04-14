
from .schema import SensorMetadata, AggregationMethod
from .loader import fetch_sensor_data

import pandas as pd

from typing import Optional, Tuple, List, Dict


async def get_sensor_data(requested_sensor_id: str) -> Tuple[pd.DataFrame, SensorMetadata]:
    sensor_data = await fetch_sensor_data(requested_sensor_id)

    metadata: Dict = sensor_data.get('metadata', {})
    values: List[Dict] = sensor_data.get('data', [])

    metadata: SensorMetadata = {
        'sensor_urn': metadata.get('sensor_urn'),
        'sensor_type': metadata.get('sensor_type'),
        'sensor_id': metadata.get('sensor_id'),
        'sensor_unit': metadata.get('display_unit', ''),
        'sensor_name': metadata.get('sensor_name'),
        'sensor_alias': metadata.get('sensor_alias')
    }

    data = pd.DataFrame(values, index=None)

    '''
    # Filter the sensor required (only one for now)
    if requested_sensor_id is not None:
        data = data.where(data['HISTORY_ID'].str.split('/')[-1] == requested_sensor_id)
    elif requested_sensor_type is not None:
        data = data.where(data['sensor_type'] == requested_sensor_type)
    else:
        # Nothing is known, raise error
        pass
    '''

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
        if m == "min":
            aggregation = AggregationMethod.MINIMUM
        elif m == "max":
            aggregation = AggregationMethod.MAXIMUM
        elif m == "average":
            aggregation = AggregationMethod.AVERAGE
    return aggregation
