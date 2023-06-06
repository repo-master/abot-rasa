'''APIs for data analysis'''

from ..client import StatAPIClient

import pandas as pd


async def outliers(data: pd.DataFrame) -> pd.DataFrame:
    '''Detect outliers in the "value" column'''
    async with StatAPIClient() as client:
        # Send DataFrame and parameters
        response = await client.post("/statistics/outliers", json={
            # DataIn
            "data": data,
            "index_column_names": "timestamp",
            "datetime_column_names": "timestamp",

            # OutliersIn
            "outliers_column": "value"
        })
        response.raise_for_status()
        return pd.DataFrame(response.json())

__all__ = [
    'outliers'
]
