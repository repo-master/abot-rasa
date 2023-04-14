# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import ActionExecutionRejected

from .api.aggregation import (
    get_sensor_data,
    determine_user_request_sensor_id,
    perform_aggregation_on_data,

    user_to_sensor_type,
    user_to_aggregation_type
)

from rasa_sdk.types import DomainDict
from typing import Any, Text, Dict, List


class ActionMetricAggregate(Action):
    def name(self):
        return "action_metric_aggregate"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        user_req_metric = tracker.get_slot("metric")
        user_req_location = tracker.get_slot("location")
        user_req_agg_method: str = tracker.get_slot("aggregation")

        print("Got slots: Metric: %s, Location: %s, Aggregation: %s" % (
            user_req_metric, user_req_location, user_req_agg_method), flush=True)

        # TODO: More assumption magic needed

        # Either one can be set
        requested_sensor_id = await determine_user_request_sensor_id(
            sensor_type=user_req_metric,
            sensor_name=None, # TODO: Get from slot
            location=user_req_location
        )

        # Could not determine the sensor to get info on (or no info provided at all)
        if requested_sensor_id is None:
            dispatcher.utter_message("Which sensor do you want to get information on?")
            return [ActionExecutionRejected(self.name())]

        # Check aggregation method provided by the user
        aggregation = user_to_aggregation_type(user_req_agg_method)

        # Load data
        data, metadata = await get_sensor_data(requested_sensor_id)

        # Run aggregation
        aggregated_result = perform_aggregation_on_data(data, aggregation, metadata)

        if aggregated_result:
            # Generate response sentence
            fmt_options = {
                # Add any other options here to pass to the below format string
                **aggregated_result
            }

            response_text = "The {aggregation_method} value of {sensor_name} is {result_value}".format(**fmt_options)

            # Say the sentence
            dispatcher.utter_message(response_text)
        else:
            dispatcher.utter_message("Sorry, data for {sensor_type} isn't available yet.".format(
                sensor_type=metadata['sensor_type']
            ))

        return []
