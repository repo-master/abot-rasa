
from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet

from .schemas import DataLoaderRequest
from .loader import request_json
from ..client import FulfillmentContext

from typing import List, Dict, Any, Optional


def update_loader_config(tracker: Tracker, options: DataLoaderRequest) -> List[Dict]:
    tracker.slots.update({"data_loader": options})
    return [
        SlotSet("data_loader", options)
    ]


async def request_data(tracker: Optional[Tracker] = None, options: Optional[DataLoaderRequest] = None) -> Any:
    if options is None and tracker is not None:
        options = tracker.slots.get("data_loader")
    if options is None:
        raise ValueError("Don't know how to load the data")

    with FulfillmentContext(tracker):
        return await request_json(options)
