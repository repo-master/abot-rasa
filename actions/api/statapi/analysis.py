'''APIs for data analysis'''

from ..client import Client

import pandas as pd


async def outliers(data: pd.DataFrame):
    '''Detect outliers in the "value" column'''
    async with Client() as client:
        # Send DataFrame and parameters
        response = await client.post("/statistics/outliers", json={
            #DataIn
            "data": data.to_dict(orient='records'),

            #OutliersIn
            "outliers_column": "value"
        })
        response.raise_for_status()
        return response.json()

__all__ = [
    'outliers'
]
