
from typing import Optional, Tuple

import pandas as pd

from .schema import AggregationMethod, AggregationResult, SensorMetadata


def sensor_name_coalesce(meta: SensorMetadata) -> str:
    return meta.get('sensor_alias') or \
        meta.get('sensor_name') or \
        meta.get('sensor_urn')


def get_outliner(df: pd.DataFrame, metadata: SensorMetadata, key_row='timestamp', value_row='value') -> pd.DataFrame:
    # Calculate the IQR of the value column
    Q1 = df[value_row].quantile(0.25)
    Q3 = df[value_row].quantile(0.75)
    IQR = Q3 - Q1

    # Define the outlier threshold
    threshold = (Q1 - 1.5*IQR, Q3 + 1.5*IQR)

    # Identify the outliers
    outliers = df.copy()
    outliers["display_unit"] = metadata['display_unit']
    outliers["is_extreme_high"] = (outliers[value_row] > threshold[1])
    outliers["is_extreme_low"] = (outliers[value_row] < threshold[0])
    outliers = outliers[outliers["is_extreme_high"] | outliers['is_extreme_low']]
    # result = {}
    # for i, row in outliers.iterrows():
    #     result[row[key_row].strftime('%Y-%m-%d %H:%M:%S.%f')] = row[value_row]
    return outliers


def perform_aggregation_on_data(
        data: pd.DataFrame,
        agg_method: AggregationMethod,
        metadata: SensorMetadata) -> Optional[AggregationResult]:

    if len(data) == 0:
        return

    result_current = "%.2f%s" % (data['value'].iloc[0], metadata['display_unit'])
    result_mean = "%.2f%s" % (data['value'].mean(), metadata['display_unit'])
    result_max = "%.2f%s" % (data['value'].max(), metadata['display_unit'])
    result_min = "%.2f%s" % (data['value'].min(), metadata['display_unit'])

    if agg_method == AggregationMethod.CURRENT:
        response_string = "The current value of {sensor_name} is {result_current}"

    if agg_method == AggregationMethod.AVERAGE:
        response_string = "The average value of {sensor_name} is {result_mean}"

    if agg_method == AggregationMethod.MAXIMUM:
        response_string = "The maximum value of {sensor_name} is {result_max}"

    if agg_method == AggregationMethod.MINIMUM:
        response_string = "The minimum value of {sensor_name} is {result_min}"

    if agg_method == AggregationMethod.SUMMARY:
        response_string = """
Here is the summary for {sensor_name}:
- Current value: {result_current}
- Average value: {result_mean}
- Maximum value: {result_max}
- Minimum value: {result_min}
""".strip()

    return {
        'result_format': response_string,
        'sensor_name': sensor_name_coalesce(metadata),
        'aggregation_method': agg_method.value,

        'result_current': result_current,
        'result_mean': result_mean,
        'result_max': result_max,
        'result_min': result_min
    }
