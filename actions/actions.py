# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

from datetime import datetime, timedelta

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
<<<<<<< HEAD
<<<<<<< HEAD
from rasa_sdk.events import ActionExecutionRejected
# from rasa_sdk.forms import FormAction
from rasa_sdk.forms import FormValidationAction
=======
from rasa_sdk.events import ActionExecutionRejected, SlotSet
>>>>>>> master
=======
from rasa_sdk.events import ActionExecutionRejected, SlotSet
>>>>>>> master

from .api.aggregation import (
    get_sensor_data,
    determine_user_request_sensor,
    perform_aggregation_on_data,

    user_to_sensor_type,
    user_to_aggregation_type
)

from rasa_sdk.types import DomainDict
from typing import Any, Text, Dict, List, Union, TypedDict, Optional
from io import BytesIO
from PIL import Image
import base64


TimeRangeIn = TypedDict("TimeRange", {"from": str, "to": str})
TimeRange = TypedDict("TimeRange", {"from": str, "to": str})


class ActionMetricAggregate(Action):
    def name(self):
        return "action_metric_aggregate"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []

        user_req_metric = tracker.get_slot("metric")
        user_req_location = tracker.get_slot("location")
        user_req_agg_method: str = tracker.get_slot("aggregation")
        user_req_timeperiod: Optional[Union[TimeRangeIn, str]] = tracker.get_slot("timestamp_agg_period")

        print("Got slots: Metric: %s, Location: %s, Aggregation: %s" % (
            user_req_metric, user_req_location, user_req_agg_method), flush=True)
        print("Time period:", user_req_timeperiod)

        # TODO: More assumption magic needed

        # Either one can be set
        requested_sensor = await determine_user_request_sensor(
            sensor_type=user_req_metric,
            sensor_name=None,  # TODO: Get from slot
            location=user_req_location
        )

        # Could not determine the sensor to get info on (or no info provided at all)
        if requested_sensor is None:
            # TODO: Please improve the sentence to be more friendly.
            dispatcher.utter_message(f" Sensor: {user_req_metric} Does not exist at location : {user_req_location}, please Enter proper data for the same")
            # HACK: Had to disable this due to above message dispatch
            return [] # [ActionExecutionRejected(self.name())]

        # Recover sensor id field
        requested_sensor_id: int = requested_sensor['sensor_id']

        # Check aggregation method provided by the user
        aggregation = user_to_aggregation_type(user_req_agg_method)

        if user_req_timeperiod is None:
            # If nothing provided (no slot set), assume today
            user_req_timeperiod = {"from": datetime.today().isoformat(), "to": datetime.now().isoformat()}
            events.append(SlotSet("timestamp_agg_period", user_req_timeperiod))

        if isinstance(user_req_timeperiod, str):
            # Single time is found, this may be start time ("today", "yesterday").
            # TODO: It may also be end time ("give me result of previous week", end time is end of week)
            user_req_timeperiod = {"from": user_req_timeperiod, "to": datetime.now().isoformat()}
            events.append(SlotSet("timestamp_agg_period", user_req_timeperiod))

        requested_timeperiod: TimeRange = {
            'from': datetime.fromisoformat(user_req_timeperiod['from']),
            'to': datetime.fromisoformat(user_req_timeperiod['to'])
        }

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
        # user_req_metric = tracker.get_slot("metric")
        # user_req_location = tracker.get_slot("location")

        # timestamp_from = datetime.today() - timedelta(days=365)
        # timestamp_to = datetime.now()

        # print("Got slots: Metric: %s, Location: %s" % (
        #     user_req_metric, user_req_location), flush=True)

        # requested_sensor_id = await determine_user_request_sensor(
        #     sensor_type=user_req_metric,
        #     sensor_name=None,  # TODO: Get from slot
        #     location=user_req_location
        # )

        # # Could not determine the sensor to get info on (or no info provided at all)
        # if requested_sensor_id is None:
        #     dispatcher.utter_message("Which sensor do you want to get information on?")
        #     return [ActionExecutionRejected(self.name())]

        # # Load data
        # data, metadata = await get_sensor_data(requested_sensor_id, timestamp_from , timestamp_to)

        # TODO: Above logic into here

        dispatcher.utter_message(image="https://images.pexels.com/photos/45201/kitty-cat-kitten-pet-45201.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2")

        return []


class ActionFormInfo(FormValidationAction):
    def name(self) -> Text:
        """Unique identifier of the form"""

        return "form_info"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        """A list of required slots that the form has to fill"""

        return ["NAME", "BRAND"]

    def submit(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Define what the form has to do
            after all required slots are filled"""

        # utter submit template
        dispatcher.utter_message(template="utter_submit", name=tracker.get_slot('NAME'),
                                 headset=tracker.get_slot('BRAND'))
        return []

    def slot_mappings(self) -> Dict[Text, Union[Dict, List[Dict]]]:
        """A dictionary to map required slots to
            - an extracted entity
            - intent: value pairs
            - a whole message
            or a list of them, where a first match will be picked"""
        print("MAppping slots")

        return {
            "name": [self.from_entity(entity="NAME", intent='my_name_is'),
                     self.from_text()],
            "headset": [self.from_entity(entity="BRAND", intent="headset"),
                        self.from_text()],
        }

    @staticmethod
    def brand_db() -> List[Text]:
        """Database of supported cuisines"""

        return [
            "samsung",
            "One plus",
            "I-phone",
        ]

    def validate_brand(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate cuisine value."""
        print(value)
        if value.lower() in self.cuisine_db():
            # validation succeeded, set the value of the "cuisine" slot to value
            return {"BRAND": value}
        else:
            print(value)
            dispatcher.utter_message(template="utter_wrong_value")
            # validation failed, set this slot to None, meaning the
            # user will be asked for the slot again
            return {"BRAND": None}
