
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from typing import List, Dict, Any

class ActionMetricSummarize(Action):
    def name(self):
        return "action_metric_summarize"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[str, Any]]:
        # user_req_metric = tracker.get_slot("metric")
        # user_req_location = tracker.get_slot("location")

        # # FIXME: Copy-pasted from above. Do whatever changes here that is done above.
        # print("Got slots: Metric: %s, Location: %s" % (
        #     user_req_metric, user_req_location), flush=True)

        # # Either one can be set
        # requested_sensor_id = await determine_user_request_sensor(
        #     sensor_type=user_req_metric,
        #     sensor_name=None,  # TODO: Get from slot
        #     location=user_req_location
        # )

        # # Could not determine the sensor to get info on (or no info provided at all)
        # if requested_sensor_id is None:
        #     dispatcher.utter_message("Which sensor do you want to get information on?")
        #     return [ActionExecutionRejected(self.name())]

        return []

