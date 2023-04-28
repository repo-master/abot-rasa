
from rasa_sdk.interfaces import Tracker
from rasa_sdk.events import SlotSet

from datetime import datetime
from actions.duckling import GRAINS, relativedelta

from typing import Optional, TypedDict, Union, Dict, List


TimeRangeIn = Union[TypedDict("TimeRangeISO8601", {"from": str, "to": str}), str]
TimeRange = TypedDict("TimeRange", {"from": datetime, "to": datetime, "user_time_entity": str, "user_time_grain": str})


def user_to_timeperiod(tracker: Tracker, events: list) -> TimeRange:
    user_req_timeperiod: Optional[TimeRangeIn] = tracker.get_slot("timestamp_agg_period")
    sys_timerange: Optional[TimeRange] = tracker.slots.get("timestamp_agg_timerange", {})
    duckling_time_entity: Dict = {}
    grain_size: Optional[str] = None

    if user_req_timeperiod is not None:
        all_entities: List = tracker.latest_message['entities']
        for e in all_entities:
            if e['entity'] == 'time' and e['extractor'] == 'DucklingEntityExtractor':
                duckling_time_entity = e

                grain_size = duckling_time_entity['additional_info'].get('grain')

                sys_timerange.update({'user_time_grain': grain_size, 'user_time_entity': duckling_time_entity['text']})

                break

    if user_req_timeperiod is None and 'from' not in sys_timerange:
        # No timestamp given. Assume for today.
        sys_timerange.update({"from": datetime.now().min})
        if 'to' not in sys_timerange:
            sys_timerange.update({"to": datetime.now()})

    if isinstance(user_req_timeperiod, str):
        # ISO 8601 timestamp received.
        # This may be start time ("today", "yesterday"), or starting point with a grain (last month => whole last month).
        if grain_size is None:
            # This actually shouldn't happen, but if it does, choose a day delta
            grain_size = 'day'

        # The given time period is the starting point of the range
        timerange_start = datetime.fromisoformat(user_req_timeperiod)

        # We need to calculate end of the range via grain size.
        # Again, the grain_size *must* be present in this dict. But if for some reason it is not, we use 1 day.
        tr_delta: relativedelta = GRAINS.get(grain_size, relativedelta(days=1))
        timerange_end = timerange_start + tr_delta

        sys_timerange.update({
            "from": timerange_start,
            "to": timerange_end
        })

    if isinstance(user_req_timeperiod, dict):
        sys_timerange.update({
            "from": datetime.fromisoformat(user_req_timeperiod['from']),
            "to": datetime.fromisoformat(user_req_timeperiod['to'])
        })

    tracker.add_slots([
        SlotSet("timestamp_agg_timerange", sys_timerange)
    ])

    return sys_timerange
