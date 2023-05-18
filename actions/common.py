
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List

import pandas as pd
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import UserUtteranceReverted
from rasa_sdk.types import DomainDict

LOG = logging.getLogger(__name__)

ACTION_STATEMENT_CONTEXT_SLOT = "statement_context"


class JSONCustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, pd.DataFrame):
            return o.to_dict(orient='records')
        if isinstance(o, pd.Series):
            return o.to_dict()
        if isinstance(o, (pd.Timestamp, datetime)):
            return o.isoformat()
        if isinstance(o, set):
            return list(o)
        LOG.warning("Custom JSON encoder couldn't encode %s.", str(type(o)))
        return super().default(o)


class ServerException(Exception):
    def __init__(self, msg, original_exc):
        super().__init__(msg)
        self._msg = msg
        self.exc = original_exc

    def __str__(self):
        return "Woops! {msg}\nPlease try again after some time.\nError reason: \"{reason}\"".format(
            msg=self._msg,
            reason="%s: %s" % (type(self.exc).__name__, str(self.exc))
        )

class ActionFailedException(Exception):
    def __init__(self, *args, print_traceback=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.tb = print_traceback

class ClientException(ActionFailedException):
    pass


def action_exception_handle_graceful(fn: Callable[[CollectingDispatcher, Tracker, DomainDict], List[Dict[str, Any]]]):
    async def _wrapper_fn(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[str, Any]]:
        try:
            return await fn(self, dispatcher, tracker, domain)
        except (ClientException, ActionFailedException) as exc:
            dispatcher.utter_message(str(exc))
            if exc.tb:
                LOG.exception("%s was generated:", str(type(exc)), exc_info=exc)
            print("Rejecting action %s" % tracker.latest_action_name)
            return [UserUtteranceReverted()]
        # Add any specific exceptions here to send response to that need a different response.
        except Exception as exc:
            LOG.exception("Unhandled exception:", exc_info=exc)
            LOG.debug("[for above exception] Current state:\n%s", str(tracker.current_state()))

            # Send exception to user. If it is `ServerException` the message will be more user-friendly.
            if not isinstance(exc, ServerException):
                # wrap exception into `ServerException`
                exc = ServerException("Something went wrong while performing your request.", exc)
            dispatcher.utter_message(text=str(exc))
            # No events are sent since it failed
            return []
    return _wrapper_fn

