# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set, Text, Tuple, Union

from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.events import FollowupAction, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict

from .api import (ConnectError, HTTPStatusError, dataapi, integration_genesis,
                  statapi)
from .api.duckling import DucklingExtraction, TimeRange
from .api.integration_genesis.schemas import SensorMetadata
from .api.statapi.schemas import AggregationMethod
from .common import (ACTION_STATEMENT_CONTEXT_SLOT, ClientException,
                     JSONCustomEncoder, ServerException,
                     action_exception_handle_graceful)
from .language_helper import summary_AggregationOut, user_to_timeperiod
from .schemas import StatementContext

LOG = logging.getLogger(__name__)


def update_statement_context(tracker: Tracker, events: list, data: StatementContext):
    curr_val = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT, {})
    if curr_val is None:
        curr_val = {}
    curr_val.update(data)
    ev = [SlotSet(ACTION_STATEMENT_CONTEXT_SLOT, curr_val)]
    tracker.add_slots(ev)
    events.extend(ev)


async def parse_input_sensor_operation(tracker: Tracker, events: List[Dict[Text, Any]]) -> Tuple[Dict, Dict]:
    user_input = {}
    parsed_input = {}

    # We need these slots
    user_req_metric: Optional[str] = tracker.get_slot("metric")
    user_req_location: Optional[str] = tracker.get_slot("location")
    user_req_agg_method: Optional[str] = tracker.get_slot("aggregation")
    user_req_timeperiod: Optional[DucklingExtraction] = tracker.get_slot("data_time_range")

    user_input.update({
        'user_req_metric': user_req_metric,
        'user_req_location': user_req_location,
        'user_req_agg_method': user_req_agg_method,
        'user_req_timeperiod': user_req_timeperiod
    })

    # Debug output
    print("Got slots: Metric: %s, Location: %s, Aggregation: %s, data_time_range: %s" % (
        user_req_metric, user_req_location, user_req_agg_method, str(user_req_timeperiod)))

    parsed_input['sensor_type'] = user_req_metric
    parsed_input['sensor_location'] = user_req_location

    parsed_input['timeperiod'] = await user_to_timeperiod(tracker, events)
    if parsed_input['timeperiod'] is None:
        raise ClientException("Need to know for what time period to load the data.")

    return parsed_input, user_input

async def reset_slot(slot_name, value, events: list ):
    events.append(SlotSet(slot_name, value))
    return events

async def search_best_matching_sensor(parsed_input: dict) -> SensorMetadata:
    try:
        # TODO: If sensor id is given, fetch metadata of it directly
        # Either one can be set
        return await integration_genesis.determine_user_request_sensor(
            sensor_type=parsed_input['sensor_type'],
            location=parsed_input['sensor_location']
        )
    except HTTPStatusError as exc:
        if exc.response.is_client_error:
            raise ClientException("No sensors of type {sensor_type} present.".format(
                sensor_type=parsed_input['sensor_type']
            ))
    except ConnectError as e:
        raise ServerException("Couldn't connect to Abot backend.", e)
    except Exception as e:  # TODO: Capture specific exceptions
        raise ServerException("Something went wrong while looking up sensor data.", e)

def exit_reject_sensor_data_incorrect(
        action_name: str,
        dispatcher: CollectingDispatcher,
        events: List,
        data: Dict[str, str],
        message: str = None):

    if message is None:
        message = "No sensors of type {user_req_metric} present%s." % (
            ' at location \"{user_req_location}\"' if ('user_req_location' in data.keys() and data['user_req_location']) else ''
        )

    dispatcher.utter_message(text=message.format(**data))

    # HACK: Had to disable this due to above message dispatch
    # events.extend([ActionExecutionRejected(action_name)])

    return events


class ActionSensorDataLoad(Action):
    '''Loads sensor data with requested parameters'''

    def name(self):
        return "action_sensor_data_load"

    @action_exception_handle_graceful
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []
        parsed_input, user_input = await parse_input_sensor_operation(tracker, events)

        requested_sensor = await search_best_matching_sensor(parsed_input)

        print(requested_sensor)

        events = await reset_slot(slot_name="metric",value=requested_sensor["sensor_type"], events=events)        
        events = await reset_slot(slot_name="location",value=requested_sensor["sensor_location"]['unit_alias'], events=events)        
        events = await reset_slot(slot_name="sensor_name",value=requested_sensor['sensor_name'], events=events)        


        await dataapi.cached_loader(
            'sensor',
            loader = integration_genesis.get_sensor_data,
            metadata = requested_sensor,
            fetch_range = parsed_input['timeperiod']
        )
        events.append(SlotSet("data_source", 'sensor'))

        return events

        # TODO: More assumption magic needed

        # TODO: Run checks on above
        # TODO: Save data into context memory
        # --- Store dataframe in memory with ID. If user requests different dataset, add new ID.
        # --- Save ID in context memory, keep using it from there.
        # TODO: Do analysis (outliers, missing, etc.) when data is loaded ONLY.

        if response_data is None:
            dispatcher.utter_message("Sorry, data for {sensor_req} isn't available.".format(
                sensor_req=user_input.get('user_req_metric')
            ))
        else:
            data, metadata = response_data

            if data.empty:
                dispatcher.utter_message("Sorry, data for {sensor_type} isn't available for the time range.".format(
                    sensor_type=metadata['sensor_type']
                ))
            else:
                # Any special things found with the data for further analysis
                data_insights = []

                # Run aggregation
                aggregated_result, outliers_result = await asyncio.gather(
                    statapi.aggregation(data, aggregation),
                    statapi.outliers(data)
                )

                agg_response_text = summary_AggregationOut(aggregated_result, unit_symbol=metadata["display_unit"])
                dispatcher.utter_message(agg_response_text)

                aggregation_followup_response_buttons: List[Dict[str, str]] = []

                # aggregation_followup_response_buttons.extend([
                #     {"title": "Min", "payload": "minimum"},
                #     {"title": "Max", "payload": "maximum"},
                #     {"title": "Average", "payload": "average"},
                #     {"title": "Current", "payload": "current"}
                # ])

                if not outliers_result.empty:
                    dispatcher.utter_message(
                        "Discovered {outlier_count} outlier value(s) within the data.".format(
                            outlier_count=outliers_result['value'].count()
                        )
                    )

                    # Button to display outlier's info
                    # aggregation_followup_response_buttons.append({
                    #     "title": "Outlier details",
                    #     "payload": "describe the outlier"
                    # })

                    for _, outlier_ser in outliers_result.iterrows():
                        data_insights.append({
                            "type": "outlier",
                            "data_point": outlier_ser
                        })

                # TODO: When UI is ready, enable this
                # dispatcher.utter_message(
                #     "Additional actions",
                #     buttons=aggregation_followup_response_buttons
                # )

                update_statement_context(tracker, events, {
                    "intent_used": tracker.latest_message.get('intent'),
                    "action_performed": self.name(),
                    "extra_data": json.dumps({
                        "insights": data_insights,
                        "operation": "aggregation",
                        "result": aggregated_result
                    }, cls=JSONCustomEncoder)
                })

        return events


class ActionFetchReport(Action):
    def name(self) -> Text:
        return "action_fetch_report"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []
        parsed_input, user_input = await parse_input_sensor_operation(tracker, events)
        requested_sensor = await search_best_matching_sensor(parsed_input)


        events = await reset_slot(slot_name="metric",value=requested_sensor["sensor_type"] , events=events)        
        events = await reset_slot(slot_name="location",value=requested_sensor["sensor_location"]['unit_alias'], events=events)        
        events = await reset_slot(slot_name="sensor_name",value=requested_sensor['sensor_name'], events=events)        

        # Recover sensor id field
        requested_sensor_id: int = requested_sensor['sensor_id']

        # Time period of aggregation
        requested_timeperiod: TimeRange = parsed_input.get('timeperiod')

        # URI or Data URI of preview image
        try:
            report_data: dict = await integration_genesis.get_report_generate_preview(requested_sensor_id, requested_timeperiod["from"], requested_timeperiod["to"])

            preview_image_url: Optional[str] = report_data.get('preview_image')
            interactive_plot: Optional[dict] = report_data.get('plot_interactive')

            # "Okay, here is the report plot. You can click [here]({report_url}) to view the interactive report."
            message = dict()
            message['text'] = "Okay, here is the report plot."
            if preview_image_url:
                message['image'] = preview_image_url
            if interactive_plot:
                message['custom'] = interactive_plot

            dispatcher.utter_message(**message)
            dispatcher.utter_message(response="utter_did_that_help")
            #events.append(FollowupAction("utter_did_that_help"))
        except HTTPStatusError as exc:
            if exc.response.is_client_error:
                raise ClientException(
                    "Sorry, No data found for sensor at the given time range.")

        return events


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

        return {
            "metric": [self.from_entity(entity="metric", intent='query_metric_aggregate'),
                       self.from_text()],
            "location": [self.from_entity(entity="location", intent="query_metric_aggregate"),
                         self.from_text()],
        }


class ActionShowSensorList(Action):
    def name(self):
        return "action_show_sensor_list"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        try:
            sensors = await integration_genesis.query_sensor_list()
        except ConnectError as e:
            raise ServerException("Couldn't connect to Abot backend.", e)

        if len(sensors) == 0:
            dispatcher.utter_message(text="No sensors available.")
        else:
            dispatcher.utter_message(text="I found %d sensor(s) :" % len(sensors))
            sensorlist_msg: str = ""
            for sensor in sensors:
                sensor_name = integration_genesis.sensor_name_coalesce(sensor)
                sensor_location = integration_genesis.unit_name_coalesce(sensor["sensor_location"])
                sensor_type = sensor["sensor_type"]
                display_unit = sensor["display_unit"]
                sensorlist_msg += f"- {sensor_name} [measures {sensor_type} ({display_unit})] at {sensor_location}\n"
            dispatcher.utter_message(text=sensorlist_msg)

        return []

class ActionGetSensor(Action):
    def name(self):
        return "action_search_sensor_by_name"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []
        print("Runing action_search_sensor_by_name")
        sensor_name: Optional[str] = tracker.get_slot("sensor_name")
        print("slot sensor_name filled with ", sensor_name)
        try:
            sensor = await integration_genesis.determine_user_request_sensor(
                sensor_name=sensor_name,  # TODO: Get from slot
            )
            events = await reset_slot(slot_name="metric",value=sensor["sensor_type"], events=events)
            events = await reset_slot(slot_name="location",value=sensor["sensor_location"]['unit_alias'], events=events)
            dispatcher.utter_message(text=f"found sensor as to be : {sensor}")
        except HTTPStatusError as exc:
            if exc.response.is_client_error:
                raise ClientException("Requested data does not exist.")
        except ConnectError as e:
            raise ServerException("Couldn't connect to Abot backend.", e)
        except Exception as e:  # TODO: Capture specific exceptions
            raise ServerException("Something went wrong while looking up sensor data.", e)
        return events 


class ActionShowLocationList(Action):
    def name(self) -> Text:
        return "action_show_location_list"
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        return []

class ActionShowTimerangeValue(Action):
    def name(self) -> Text:
        return "action_ask_data_value_timerange"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        HUMAN_TIME_FORMAT = "%c"
        time_range = await user_to_timeperiod(tracker, autoset_default=None)
        if time_range:
            dispatcher.utter_message(text="Data time range: {t_from} till {t_to}".format(
                t_from=time_range["from"].strftime(HUMAN_TIME_FORMAT),
                t_to=time_range["to"].strftime(HUMAN_TIME_FORMAT)
            ))
        else:
            dispatcher.utter_message(text="Time range is not provided for data.")
        return []


class ActionShowLocationValue(Action):
    def name(self) -> Text:
        return "action_ask_data_value_location"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        user_req_location: Optional[str] = tracker.get_slot("location")
        if user_req_location:
            dispatcher.utter_message(text="Location: %s" % user_req_location)
        else:
            dispatcher.utter_message(text="Location is not provided for data.")
        return []
