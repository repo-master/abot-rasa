'''APIs for data aggregation'''

from ..client import StatAPIClient

from .schemas import AggregationMethod, AggregationOut

import pandas as pd

from typing import Union, Set


async def aggregation(data: pd.DataFrame,
                      method: Union[AggregationMethod, Set[AggregationMethod]] = AggregationMethod.RECENT,
                      **options
                      ) -> AggregationOut:
    '''Perform aggregation using given method on the "value" column'''
    async with StatAPIClient() as client:
        # Send DataFrame and parameters
        response = await client.post("/statistics/aggregation", json={
            # DataIn
            "data": data,
            "index_column_names": "timestamp",
            "datetime_column_names": "timestamp",

            # AggregationIn
            "method": method,
            "aggregation_column": "value",
            "aggregation_options": options
        })
        response.raise_for_status()
        return response.json()

__all__ = [
    'aggregation'
]
