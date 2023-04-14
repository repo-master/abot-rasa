
from .schema import SensorMetadata, AggregationMethod
from .loader import fetch_sensor_data

import pandas as pd

from typing import Optional, Tuple


async def get_sensor_data(requested_sensor_id: Optional[str] = None,
                          requested_sensor_type: Optional[str] = None) -> Tuple[pd.DataFrame, SensorMetadata]:

    sensor_data = await fetch_sensor_data(requested_sensor_id, requested_sensor_type)
    print(sensor_data)

    # TODO: Remove read_csv, use above data

    data = pd.read_csv("sensor_data_dummy.csv")
    data['TIMESTAMP'] = pd.to_datetime(data['TIMESTAMP'])
    data.sort_values('TIMESTAMP', ascending=False, inplace=True)

    # Filter the sensor required (only one for now)
    if requested_sensor_id is not None:
        data = data.where(data['HISTORY_ID'].str.split('/')[-1] == requested_sensor_id)
    elif requested_sensor_type is not None:
        data = data.where(data['sensor_type'] == requested_sensor_type)
    else:
        # Nothing is known, raise error
        pass

    data.dropna(inplace=True)

    if len(data) > 0:
        first_row = data.iloc[0]

        # TODO: This will also be gathered from a query
        metadata: SensorMetadata = {
            'sensor_id': first_row['HISTORY_ID'],
            'sensor_type': first_row['sensor_type'],
            'sensor_unit': ''
        }
        set_sensor_units_from_type(metadata)
    else:
        metadata: SensorMetadata = {
            'sensor_id': None,
            'sensor_type': requested_sensor_type,
            'sensor_unit': ''
        }

    return data, metadata


def set_sensor_units_from_type(metadata: SensorMetadata):
    if metadata.get('sensor_type') is None:
        # TODO: Warning of some sorts
        pass
    SENSORTYPE_UNIT_MAP = {
        'temp': '\u2103',  # degree C symbol
        'rh': '%'
    }
    # Assign the unit if possible, else it is set to ''
    metadata['sensor_unit'] = SENSORTYPE_UNIT_MAP.get(metadata['sensor_type'], '')


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
