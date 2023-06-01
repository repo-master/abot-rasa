
from typing import Any, Dict, List, Optional, Set, Union

import pandas as pd
from rasa_sdk.events import FollowupAction, SlotSet
from rasa_sdk.interfaces import Tracker

from .api.duckling import DucklingExtraction, TimeRange, extract_fromto, parse as duckling_parse
from .api.statapi.schemas import AggregationMethod, AggregationOut
from actions.common import ActionFailedException


def user_to_aggregation_type(name: Optional[Union[str, List[str]]]) -> Union[AggregationMethod, Set[AggregationMethod]]:
    aggregation = AggregationMethod.RECENT

    if name is not None:
        if isinstance(name, list) and len(name) == 1:
            name = name[0]
        if isinstance(name, str):
            aggregation = AggregationMethod(name.lower())
        elif isinstance(name, list):
            aggregation = set(map(lambda n: AggregationMethod(n.lower()), name))

    return aggregation


async def user_to_timeperiod(tracker: Tracker, events: Optional[list] = None, autoset_default: Optional[str] = "today") -> Optional[TimeRange]:
    user_req_timeperiod: Optional[Union[DucklingExtraction, List[str], str]] = tracker.get_slot("data_time_range")

    if user_req_timeperiod is None:
        if autoset_default is not None:
            # No timestamp given. Assume for today (or given value).
            today_entities = await duckling_parse(autoset_default)
            user_req_timeperiod = today_entities[0]
            if events is not None:
                events.append(SlotSet("data_time_range", user_req_timeperiod))
        else:
            return
    elif isinstance(user_req_timeperiod, str):
        # TODO
        return

    parsed_timerange = extract_fromto(user_req_timeperiod)
    if parsed_timerange is None:
        raise ActionFailedException("Unable to understand timerange given for \"%s\"" % tracker.latest_message["text"])

    return parsed_timerange

def string_timestamp_to_human(ts_raw: str) -> str:
    ts = pd.to_datetime(ts_raw)
    return ts.strftime("%c")

def summary_AggregationOut(agg: AggregationOut, unit_symbol: str = '', **kwargs) -> str:
    def _agg_str(am: AggregationMethod, value: Union[float, int]) -> str:
        if am == AggregationMethod.COMPLIANCE:
            # Compliance needs to be shown as percent
            return '{agg_method}: {value:.2f}%'.format(
                agg_method=am.value.title(),
                value=value*100
            )
        if am == AggregationMethod.QUANTILE:
            # Quantile shown with the requested value
            return '{percentile}{agg_method}: {value:.2f}{unit_symbol}'.format(
                percentile=kwargs.get('quantile_size', ''),
                agg_method=am.value.title(),
                value=value,
                unit_symbol=unit_symbol
            )
        if am == AggregationMethod.COUNT:
            return '{agg_method}: {value}'.format(
                agg_method=am.value.title(),
                value=int(value)
            )
        return '{agg_method}: {value:.2f}{unit_symbol}'.format(
            agg_method=am.value.title(),
            value=value,
            unit_symbol=unit_symbol
        )

    if len(agg.keys()) == 1:
        # Directly give that value without a list
        am, val = next(iter(agg.items()))
        return _agg_str(AggregationMethod(am), val)
    elif len(agg.keys()) > 1:
        # Prepare a markdown list-style output
        return '\n'.join(["- " + _agg_str(AggregationMethod(am), val) for am, val in agg.items()])
