
from enum import Enum
from typing import TypedDict, Optional


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
    sensor_id: Optional[str]
    sensor_type: str
    sensor_unit: str
