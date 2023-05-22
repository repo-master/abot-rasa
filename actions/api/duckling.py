
from typing import List, TypedDict, Union, Optional

import pandas as pd
from dateutil.relativedelta import relativedelta

from .client import DucklingClient

DucklingExtraction = TypedDict("DucklingExtraction", {"body": str})
TimeRange = TypedDict("TimeRange", {"from": pd.Timestamp, "to": pd.Timestamp,
                      "user_time_entity": str, "user_time_grain": str})


GRAINS = {
    'second': relativedelta(seconds=1),
    'minute': relativedelta(minutes=1),
    'hour': relativedelta(hours=1),
    'day': relativedelta(days=1),
    'week': relativedelta(weeks=1),
    'month': relativedelta(months=1),
    'quarter': relativedelta(months=3),
    'year': relativedelta(years=1)
}


def extract_fromto(duckling_input: DucklingExtraction) -> Optional[TimeRange]:
    if duckling_input.get('dim') != "time":
        return
    is_interval = duckling_input['value'].get('type') == 'interval'

    val_obj = duckling_input.get('value', {})
    time_from = None
    time_to = None
    grain_size = None

    if is_interval:
        time_from = val_obj.get("from")['value']
        time_to = val_obj.get("to")['value']
    else:
        grain_entity: str = val_obj.get('grain', '')
        grain_size = GRAINS.get(grain_entity.lower())
        time_from = val_obj.get("value")

    time_from = pd.to_datetime(time_from, errors='raise')
    if time_to is not None:
        time_to = pd.to_datetime(time_to, errors='raise')
    elif grain_size is not None:
        time_to = time_from + grain_size

    return {
        "from": time_from,
        "to": time_to,
        "user_time_grain": grain_size,
        "user_time_entity": duckling_input.get('body')
    }


async def parse(text: Union[str, List[str]]) -> List[DucklingExtraction]:
    async with DucklingClient() as client:
        response = await client.post("/parse", data={
            "text": text,
            "dims": ["time", "number"],
            "locale": "en_IN",
            "tz": "Asia/Kolkata"
        })
        response.raise_for_status()
        return response.json()
