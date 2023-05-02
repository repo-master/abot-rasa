
from enum import Enum
from typing import Optional, List, Dict
from typing_extensions import TypedDict, NotRequired


class AggregationMethod(Enum):
    CURRENT = "current"
    AVERAGE = 'average'
    MINIMUM = 'minimum'
    MAXIMUM = 'maximum'
    SUMMARY = 'summary'


class AggregationResult(TypedDict):
    result_format: str
    sensor_name: str
    aggregation_method: str
    outliers: dict


class SensorMetadata(TypedDict):
    sensor_urn: str
    sensor_id: NotRequired[int]
    sensor_name: NotRequired[str]
    sensor_alias: NotRequired[str]
    sensor_type: str
    display_unit: str


class SensorDataResponse(TypedDict):
    metadata: SensorMetadata
    data: List[Dict]
