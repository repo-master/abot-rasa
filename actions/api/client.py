
import urllib.parse
from typing import Optional
from contextlib import contextmanager

from rasa_sdk import Tracker
from httpx import AsyncClient, ConnectError, HTTPStatusError

from ..common import ClientException
from .config import BACKEND_ENDPOINT_BASE, DUCKLING_HTTP_URL
from .httpx_patches import monkeypatch_httpx

fulfillment_context_id: Optional[int] = None

# Monkeypatch httpx to fix json encoder
monkeypatch_httpx()


@contextmanager
def FulfillmentContext(tracker: Tracker):
    global fulfillment_context_id
    old_fulfillment_context_id = fulfillment_context_id
    fulfillment_context_id = tracker.slots.get('fulfillment_id')
    yield
    fulfillment_context_id = old_fulfillment_context_id


def StatAPIClient(**kwargs) -> AsyncClient:
    return AsyncClient(base_url=BACKEND_ENDPOINT_BASE, timeout=60.0, **kwargs)


def FulfillmentClient(**kwargs) -> AsyncClient:
    # global fulfillment_context_id
    # if fulfillment_context_id is None:
    #     raise ClientException("No service selected for performing this action.", print_traceback=False)
    # try:
    #     fulfillment_id: int = int(fulfillment_context_id)
    # except:
    #     # TODO: Failsafe
    #     fulfillment_id = 1
    # fulfillment_url_base = urllib.parse.urljoin(BACKEND_ENDPOINT_BASE, "/fulfillment/%d" % fulfillment_id)
    return AsyncClient(base_url=BACKEND_ENDPOINT_BASE, timeout=60.0, **kwargs)


def DucklingClient(**kwargs) -> AsyncClient:
    return AsyncClient(base_url=DUCKLING_HTTP_URL, timeout=60.0, **kwargs)
