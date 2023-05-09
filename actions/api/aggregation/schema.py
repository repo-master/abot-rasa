
from typing_extensions import TypedDict


class AggregationResult(TypedDict):
    result_format: str
    sensor_name: str
    aggregation_method: str
    outliers: dict
