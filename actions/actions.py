# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

from datetime import datetime, timedelta
import urllib.parse

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import ActionExecutionRejected, SlotSet

from .api.aggregation import (
    get_sensor_data,
    get_report_generate_preview,

    determine_user_request_sensor,
    perform_aggregation_on_data,

    user_to_sensor_type,
    user_to_aggregation_type,

    SensorMetadata,
    AggregationMethod
)

from rasa_sdk.types import DomainDict
from typing import Any, Text, Dict, List, Tuple, Union, TypedDict, Optional
from io import BytesIO
from PIL import Image
import base64


TimeRangeIn = TypedDict("TimeRangeIn", {"from": str, "to": str})
TimeRange = TypedDict("TimeRange", {"from": datetime, "to": datetime})


async def parse_input_sensor_operation(dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Tuple[Dict, List[Dict[Text, Any]]]:
    events: List[Dict[str, Any]] = []
    user_input = {}

    # We need these slots
    user_req_metric: Optional[str] = tracker.get_slot("metric")
    user_req_location: Optional[str] = tracker.get_slot("location")
    user_req_agg_method: Optional[str] = tracker.get_slot("aggregation")
    user_req_timeperiod: Optional[Union[TimeRangeIn, str]] = tracker.get_slot("timestamp_agg_period")

    user_input.update({
        'user_req_metric': user_req_metric,
        'user_req_location': user_req_location,
        'user_req_agg_method': user_req_agg_method,
        'user_req_timeperiod': user_req_timeperiod
    })

    # Debug output
    print("Got slots: Metric: %s, Location: %s, Aggregation: %s, timestamp_agg_period: %s" % (
        user_req_metric, user_req_location, user_req_agg_method, user_req_timeperiod), flush=True)
    print("Time period:", user_req_timeperiod)

    try:
        # Check aggregation method provided by the user
        user_input['aggregation'] = user_to_aggregation_type(user_req_agg_method)

        if user_req_timeperiod is None:
            # TODO: This is kind-of wrong. It should not store timestamp of today, but rather calculate "today"'s time every request
            # If nothing provided (no slot set), assume today
            user_req_timeperiod = {"from": datetime.today().isoformat(), "to": datetime.now().isoformat()}
            # Update slot with this info for future conversations
            events.append(SlotSet("timestamp_agg_period", user_req_timeperiod))

        if isinstance(user_req_timeperiod, str):
            # Single time is found, this may be start time ("today", "yesterday").
            # TODO: It may also be end time ("give me result of previous week", end time is end of week)
            user_req_timeperiod = {"from": user_req_timeperiod, "to": datetime.now().isoformat()}
            events.append(SlotSet("timestamp_agg_period", user_req_timeperiod))

        user_input['timeperiod'] = {
            'from': datetime.fromisoformat(user_req_timeperiod['from']),
            'to': datetime.fromisoformat(user_req_timeperiod['to'])
        }

        # TODO: More assumption magic needed

        # Either one can be set
        user_input['sensor'] = await determine_user_request_sensor(
            sensor_type=user_req_metric,
            sensor_name=None,  # TODO: Get from slot
            location=user_req_location
        )
    finally:
        return user_input, events

def exit_reject_sensor_data_incorrect(
        action_name: str,
        dispatcher: CollectingDispatcher,
        events: List,
        data: Dict[str, str],
        message: str = None):

    # TODO: Please improve the sentence to be more friendly.
    if message is None:
        message = "Sensor: {user_req_metric} Does not exist at location : {user_req_location}, please Enter proper data for the same"

    dispatcher.utter_message(text=message.format(**data))

    # HACK: Had to disable this due to above message dispatch
    # events.extend([ActionExecutionRejected(action_name)])

    return events

class ActionMetricAggregate(Action):
    def name(self):
        return "action_metric_aggregate"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        user_input, events = await parse_input_sensor_operation(dispatcher, tracker, domain)

        requested_sensor: SensorMetadata = user_input.get('sensor')

        # Could not determine the sensor to get info on (or no info provided at all)
        if requested_sensor is None:
            return exit_reject_sensor_data_incorrect(self.name(), dispatcher, events, user_input)

        # Recover sensor id field
        requested_sensor_id: int = requested_sensor['sensor_id']

        # Check aggregation method provided by the user
        aggregation: AggregationMethod = user_input.get('aggregation')

        # Time period of aggregation
        requested_timeperiod: TimeRange = user_input.get('timeperiod')

        # TODO: Aggregation must be done on backend. Move all this to backend with API

        # Load data
        data, metadata = await get_sensor_data(requested_sensor_id, requested_timeperiod["from"], requested_timeperiod["to"])

        # TODO: Run checks on above

        # Run aggregation
        agg_response = perform_aggregation_on_data(data, aggregation, metadata)

        if agg_response:
            response_string, aggregated_result = agg_response
            # Generate response sentence
            fmt_options = {
                # Add any other options here to pass to the below format string
                **aggregated_result
            }

            response_text = response_string.format(**fmt_options)

            # Say the sentence
            dispatcher.utter_message(response_text)
        else:
            dispatcher.utter_message("Sorry, data for {sensor_type} isn't available yet.".format(
                sensor_type=metadata['sensor_type']
            ))

        return events


class ActionMetricSummarize(Action):
    def name(self):
        return "action_metric_summarize"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
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

class ActionShowImage(Action):
    def name(self) -> Text:
        return "action_show_image"
    
    def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        # dispatcher.utter_message(response="utter_show_image")
        img = Image.open("actions/logo-phAIdelta.png")

        data = BytesIO()
        img.save(data, "JPEG")
        data64 = base64.b64encode(data.getvalue()).decode('utf-8')
        uri = "data:image/jpeg;base64," + data64

        # Send the image to the user
        dispatcher.utter_message(image=uri)



        return []
    

class ActionFetchReport(Action):
    def name(self) -> Text:
        return "action_fetch_report"

    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        user_input, events = await parse_input_sensor_operation(dispatcher, tracker, domain)

        requested_sensor: SensorMetadata = user_input.get('sensor')

        # Could not determine the sensor to get info on (or no info provided at all)
        if requested_sensor is None:
            return exit_reject_sensor_data_incorrect(
                self.name(),
                dispatcher,
                events,
                user_input,
                message="Sensor information isn't provided. Unable to generate the report."
            )

        # Recover sensor id field
        requested_sensor_id: int = requested_sensor['sensor_id']

        # Time period of aggregation
        requested_timeperiod: TimeRange = user_input.get('timeperiod')

        # URI or Data URI of preview image
        report_data: dict = await get_report_generate_preview()

        # TODO: Somehow get public URL of report. localhost won't work obviously. Don't hardcode it.
        report_url: str = report_data['interactive_report_route']
        preview_image_url: str = report_data['preview_image']

        dispatcher.utter_message(
            text="Okay, here is the report plot. You can click [here]({report_url}) to view the interactive report.".format(
                report_url=report_url
            ),
            image=preview_image_url
        )

        return []

class ActionFormMetricData(FormValidationAction):
    def name(self) -> Text:
        return "form_metric_data"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        """A list of required slots that the form has to fill"""

        return ["metric", "location"]

    def submit(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Define what the form has to do
            after all required slots are filled"""

        # utter submit template
        dispatcher.utter_message(template="action_metric_aggregate", metric=tracker.get_slot('metric'),
                                 location=tracker.get_slot('location'))
        return []

    def slot_mappings(self) -> Dict[Text, Union[Dict, List[Dict]]]:
        """A dictionary to map required slots to
            - an extracted entity
            - intent: value pairs
            - a whole message
            or a list of them, where a first match will be picked"""
        print("MAppping slots")

        return {
            "metric": [self.from_entity(entity="metric", intent='query_metric_aggregate'),
                     self.from_text()],
            "location": [self.from_entity(entity="location", intent="query_metric_aggregate"),
                        self.from_text()],
        }

