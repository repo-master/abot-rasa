
import pandas as pd

from .schema import AggregationMethod, SensorMetadata, AggregationResult
from typing import Optional


def sensor_name_coalesce(meta: SensorMetadata) -> str:
    return meta.get('sensor_alias') or \
        meta.get('sensor_name') or \
        (
            'sensor ID %d (%s)' % (meta['sensor_id'], meta['sensor_type'])
        ) if meta.get('sensor_id') else meta.get('sensor_urn')

def perform_aggregation_on_data(
        data: pd.DataFrame,
        agg_method: AggregationMethod,
        metadata: SensorMetadata) -> Optional[AggregationResult]:
    result: float

    if len(data) == 0:
        return

    if agg_method == AggregationMethod.CURRENT:
        result = data['value'].iloc[0]
    if agg_method == AggregationMethod.AVERAGE:
        result = data['value'].mean()
    if agg_method == AggregationMethod.MAXIMUM:
        result = data['value'].max()
    if agg_method == AggregationMethod.MINIMUM:
        result = data['value'].min()

    return {
        'sensor_name': sensor_name_coalesce(metadata),
        'result_value': "%.2f%s" % (result, metadata['sensor_unit']),
        'aggregation_method': agg_method.value
    }
