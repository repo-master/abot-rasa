
from enum import Enum
from typing import Optional
from typing_extensions import TypedDict, NotRequired


class AggregationMethod(Enum):
    CURRENT = "current"
    AVERAGE = 'average'
    MINIMUM = 'minimum'
    MAXIMUM = 'maximum'


class AggregationResult(TypedDict):
    sensor_name: str
    result_value: str
    aggregation_method: str


class SensorMetadata(TypedDict):
    sensor_urn: str
    sensor_id: NotRequired[int]
    sensor_name: NotRequired[str]
    sensor_alias: NotRequired[str]
    sensor_type: str
    sensor_unit: str
