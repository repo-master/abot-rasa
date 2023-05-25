
from typing import Dict, List, Optional
from typing_extensions import NotRequired, TypedDict


class LocationMetadata(TypedDict):
    unit_urn: str
    unit_id: int
    unit_alias: Optional[str]


class SensorMetadata(TypedDict):
    sensor_urn: str
    sensor_id: NotRequired[int]
    sensor_name: NotRequired[str]
    sensor_alias: NotRequired[str]
    sensor_type: str
    display_unit: str
    sensor_location: NotRequired[LocationMetadata]


class SensorDataResponse(TypedDict):
    metadata: SensorMetadata
    data: List[Dict]
