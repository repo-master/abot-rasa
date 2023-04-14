
import pandas as pd

from .schema import AggregationMethod, SensorMetadata, AggregationResult
from typing import Optional


def perform_aggregation_on_data(
        data: pd.DataFrame,
        agg_method: AggregationMethod,
        metadata: SensorMetadata) -> Optional[AggregationResult]:
    result: float

    if len(data) == 0:
        return

    if agg_method == AggregationMethod.CURRENT:
        result = data['VALUE'].iloc[0]
    if agg_method == AggregationMethod.AVERAGE:
        result = data['VALUE'].mean()
    if agg_method == AggregationMethod.MAXIMUM:
        result = data['VALUE'].max()
    if agg_method == AggregationMethod.MINIMUM:
        result = data['VALUE'].min()

    return {
        'sensor_name': metadata['sensor_id'],
        'result_value': "%.2f%s" % (result, metadata['sensor_unit']),
        'aggregation_method': agg_method.value
    }
