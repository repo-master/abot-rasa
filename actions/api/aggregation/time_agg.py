
from datetime import datetime
from typing import Dict, List, Optional, TypedDict, Union

from rasa_sdk.events import SlotSet, FollowupAction
from rasa_sdk.interfaces import Tracker

import pandas as pd

from actions.duckling import GRAINS, relativedelta

TimeRangeIn = Union[TypedDict("TimeRangeISO8601", {"from": str, "to": str}), str]
TimeRange = TypedDict("TimeRange", {"from": datetime, "to": datetime, "user_time_entity": str, "user_time_grain": str})


def user_to_timeperiod(tracker: Tracker, events: list) -> TimeRange:
    user_req_timeperiod: Optional[TimeRangeIn] = tracker.get_slot("timestamp_agg_period")
    sys_timerange: Optional[TimeRange] = tracker.slots.get("timestamp_agg_timerange")
    duckling_time_entity: Optional[Dict] = None
    grain_size: Optional[str] = None

    if sys_timerange is None:
        sys_timerange: TimeRange = {}
    else:
        # Decode 'from' and 'to' fields back to datetime from isoformat-ed string
        if 'from' in sys_timerange.keys():
            sys_timerange['from'] = datetime.fromisoformat(sys_timerange['from'])
        if 'to' in sys_timerange.keys():
            sys_timerange['to'] = datetime.fromisoformat(sys_timerange['to'])

    if user_req_timeperiod is not None:
        all_entities: List = tracker.latest_message['entities']
        for e in all_entities:
            if e['entity'] == 'time' and e['extractor'] == 'DucklingEntityExtractor':
                duckling_time_entity = e

                grain_size = duckling_time_entity['additional_info'].get('grain')

                sys_timerange.update({'user_time_grain': grain_size, 'user_time_entity': duckling_time_entity['text']})

                break

    if user_req_timeperiod is None and 'from' not in sys_timerange.keys():
        # No timestamp given. Assume for today.
        sys_timerange.update({"from": datetime.combine(datetime.now(), datetime.min.time())})
        if 'to' not in sys_timerange.keys():
            sys_timerange.update({"to": datetime.now()})

    # NOTE: There is a bug with Rasa's duckling binding that only sends the grain entity once, and not on subsequent utterances.
    if isinstance(user_req_timeperiod, str):
        #if duckling_time_entity is not None:
        # ISO 8601 timestamp received.
        # This may be start time ("today", "yesterday"), or starting point with a grain (last month => whole last month).
        if grain_size is None:
            if 'user_time_grain' in sys_timerange.keys():
                grain_size = sys_timerange['user_time_grain']
            else:
                # This actually shouldn't happen, but if it does, choose a day delta
                grain_size = 'day'

        # The given time period is the starting point of the range
        try:
            timerange_start = datetime.fromisoformat(user_req_timeperiod)
        except ValueError:
            # Not received in isoformat somehow
            timerange_start = pd.to_datetime(user_req_timeperiod)

        # We need to calculate end of the range via grain size.
        # Again, the grain_size *must* be present in this dict. But if for some reason it is not, we use 1 day.
        tr_delta: relativedelta = GRAINS.get(grain_size, relativedelta(days=1))
        timerange_end = timerange_start + tr_delta

        sys_timerange.update({
            "from": timerange_start,
            "to": timerange_end
        })
        #else:
        #    # This happens if the timestamp is set previously but entity is not sent every time.
        #    pass

    if isinstance(user_req_timeperiod, dict):
        if user_req_timeperiod['from'] is not None and user_req_timeperiod['to'] is not None:
            sys_timerange.update({
                "from": datetime.fromisoformat(user_req_timeperiod['from']),
                "to": datetime.fromisoformat(user_req_timeperiod['to'])
            })

    sys_timerange_slot = {
        **sys_timerange
    }

    if 'from' in sys_timerange.keys() and 'to' in sys_timerange.keys():
        sys_timerange_slot.update({
            "from": sys_timerange['from'].isoformat(),
            "to": sys_timerange['to'].isoformat()
        })

    # If still slot didn't get set
    if not ('from' in sys_timerange_slot.keys() and 'to' in sys_timerange_slot.keys()):
        ev = [
            FollowupAction("action_listen")
        ]
        events.extend(ev)
        return

    ev = [
        SlotSet("timestamp_agg_timerange", sys_timerange_slot)
    ]
    tracker.add_slots(ev)
    events.extend(ev)

    return sys_timerange
