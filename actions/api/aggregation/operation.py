
import pandas as pd

from .schema import AggregationMethod, SensorMetadata, AggregationResult
from typing import Optional


def sensor_name_coalesce(meta: SensorMetadata) -> str:
    return meta.get('sensor_alias') or \
        meta.get('sensor_name') or \
        meta.get('sensor_urn')

def get_outliner(df, key_row='timestamp' , value_row='value'):
    # Calculate the IQR of the value column
    Q1 = df[value_row].quantile(0.25)
    Q3 = df[value_row].quantile(0.75)
    IQR = Q3 - Q1

    # Define the outlier threshold
    threshold = (Q1 - 1.5*IQR, Q3 + 1.5*IQR)

    # Identify the outliers
    outliers = df[(df[value_row] < threshold[0]) | (df[value_row] > threshold[1])]
    print("outlier data frame /n",outliers)
    result = {}
    for i, row in outliers.iterrows():
        result[row[key_row]]= row[value_row]
    return result

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
    if agg_method == AggregationMethod.SUMMARY:
        unit = metadata['sensor_unit']
        result = f" : \n\tCurrent value :{data['value'].iloc[0]}{unit} \n\tAverage value :{data['value'].mean()}{unit} \n\tMax value : {data['value'].max()}{unit} \n\tMinimum value : {data['value'].min()}"
    
    outliers = get_outliner(data)
    return {
        'sensor_name': sensor_name_coalesce(metadata),
        'result_value': f"{result}{metadata['sensor_unit']}",
        'aggregation_method': agg_method.value,
        'outliers' : outliers
    }
