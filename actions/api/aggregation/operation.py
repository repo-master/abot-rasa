
import pandas as pd

from ..dataapi.schemas import SensorMetadata


async def perform_aggregation_on_data(
        data: pd.DataFrame,
        agg_method,
        metadata: SensorMetadata):

    if len(data) == 0:
        return



    # result_current = "%.2f%s" % (data['value'].iloc[0], metadata['display_unit'])
    # result_mean = "%.2f%s" % (data['value'].mean(), metadata['display_unit'])
    # result_max = "%.2f%s" % (data['value'].max(), metadata['display_unit'])
    # result_min = "%.2f%s" % (data['value'].min(), metadata['display_unit'])

#     if agg_method == AggregationMethod.CURRENT:
#         response_string = "The most recent value of {sensor_name} is {result_current}"

#     if agg_method == AggregationMethod.AVERAGE:
#         response_string = "The average value of {sensor_name} is {result_mean}"

#     if agg_method == AggregationMethod.MAXIMUM:
#         response_string = "The maximum value of {sensor_name} is {result_max}"

#     if agg_method == AggregationMethod.MINIMUM:
#         response_string = "The minimum value of {sensor_name} is {result_min}"

#     if agg_method == AggregationMethod.SUMMARY:
#         response_string = """
# Here is the summary for {sensor_name}:
# - Current value: {result_current}
# - Average value: {result_mean}
# - Maximum value: {result_max}
# - Minimum value: {result_min}
# """.strip()

    # return {
    #     'result_format': response_string,
    #     'sensor_name': sensor_name_coalesce(metadata),
    #     'aggregation_method': agg_method.value,

    #     'result_current': result_current,
    #     'result_mean': result_mean,
    #     'result_max': result_max,
    #     'result_min': result_min
    # }
