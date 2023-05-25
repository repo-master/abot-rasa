# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Text, Tuple, Union

from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict

from .api import (ConnectError, HTTPStatusError, dataapi, integration_genesis,
                  statapi)
from .api.duckling import TimeRange
from .api.integration_genesis.schemas import SensorMetadata
from .common import (ClientException, JSONCustomEncoder, ServerException,
                     action_exception_handle_graceful)
from .language_helper import summary_AggregationOut, user_to_timeperiod

LOGGER = logging.getLogger(__name__)


async def parse_input_sensor_operation(tracker: Tracker, events: List[Dict[Text, Any]]) -> Tuple[Dict, Dict]:
    user_input = {}
    parsed_input = {}

    # We need these slots
    user_req_metric: Optional[str] = tracker.get_slot("metric")
    user_req_location: Optional[str] = tracker.get_slot("location")
    user_req_sensor_name: Optional[str] = tracker.get_slot("sensor_name")

    user_input.update({
        'user_req_metric': user_req_metric,
        'user_req_location': user_req_location,
        'user_req_sensor_name': user_req_sensor_name
    })

    # Debug output
    LOGGER.info("Got slots: Sensor-Type: %s, Location: %s, Sensor-Name: %s",
        user_req_metric, user_req_location, user_req_sensor_name)

    parsed_input['sensor_type'] = user_req_metric
    parsed_input['sensor_location'] = user_req_location
    parsed_input['sensor_name'] = user_req_sensor_name

    parsed_input['timeperiod'] = await user_to_timeperiod(tracker, events)
    if parsed_input['timeperiod'] is None:
        raise ClientException("Need to know for what time period to load the data.")

    return parsed_input, user_input


def reset_slot(slot_name, value, events: list):
    events.append(SlotSet(slot_name, value))


async def search_best_matching_sensors(parsed_input: dict) -> List[SensorMetadata]:
    try:
        # TODO: If sensor id is given, fetch metadata of it directly
        # Either one can be set
        return await integration_genesis.determine_user_request_sensor(
            sensor_type=parsed_input['sensor_type'],
            location=parsed_input['sensor_location'],
            sensor_name=parsed_input['sensor_name']
        )
    except HTTPStatusError as exc:
        if exc.response.is_client_error:
            resp = exc.response.json()
            if parsed_input['sensor_type']:
                raise ClientException("No sensors of type {sensor_type} present{loc_opt}.".format(
                    sensor_type=parsed_input['sensor_type'],
                    loc_opt='' if parsed_input['sensor_location'] is None else 'at %s' % parsed_input['sensor_location']
                ), print_traceback=False)
            elif parsed_input['sensor_name']:
                raise ClientException("Sensor named {sensor_name} not found.".format(
                    sensor_name = parsed_input['sensor_name']
                ), print_traceback=False)
            elif 'detail' in resp.keys():
                raise ClientException(resp['detail'], print_traceback=False)
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
            ' at location \"{user_req_location}\"' if (
                'user_req_location' in data.keys() and data['user_req_location']) else ''
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

        requested_sensors = await search_best_matching_sensors(parsed_input)

        requested_sensor: SensorMetadata = None

        if len(requested_sensors) == 1:
            requested_sensor = requested_sensors[0]
        elif len(requested_sensors) > 1:
            def loc_at_str(s):
                if s:
                    return ' at ' + s
                return ''
            dispatcher.utter_button_message("Which sensor? Select one:", buttons=[
                {
                    "title": "%s%s" % (
                        integration_genesis.sensor_name_coalesce(sensor_obj),
                        loc_at_str(integration_genesis.location_name_coalesce(sensor_obj.get('sensor_location')))
                    ),
                    "payload": "/activate_sensor_name_form{%s}" % (
                        json.dumps({"sensor_name": sensor_obj["sensor_name"]})
                    )
                }
                for sensor_obj in requested_sensors
            ])
            return events

        dispatcher.utter_message(text="Loading sensor %s at time range %s to %s..." % (
            integration_genesis.sensor_name_coalesce(requested_sensor),
            parsed_input['timeperiod']['from'].strftime('%c'),
            parsed_input['timeperiod']['to'].strftime('%c')
        ))

        reset_slot(slot_name="metric", value=requested_sensor["sensor_type"], events=events)
        reset_slot(slot_name="location", value=requested_sensor["sensor_location"]['unit_alias'], events=events)
        reset_slot(slot_name="sensor_name", value=requested_sensor['sensor_name'], events=events)

        await dataapi.cached_loader(
            tracker,
            'sensor',
            loader=integration_genesis.get_sensor_data,
            metadata=requested_sensor,
            fetch_range=parsed_input['timeperiod']
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

        try:
            sensor_selected = dataapi.get_cache("sensor")
            if sensor_selected is None:
                raise ClientException(
                    "Sorry, sensor data not selected. Try specifying sensor and time range.",
                    print_traceback=False)
            sensor_metadata: SensorMetadata = sensor_selected._loader_params['metadata']
            sensor_data_select_range: TimeRange = sensor_selected._loader_params['fetch_range']
            report_data: dict = await integration_genesis.get_report_generate_preview(sensor_metadata, sensor_data_select_range)

            preview_image_url: Optional[str] = report_data.get('preview_image')
            interactive_plot: Optional[dict] = report_data.get('plot_interactive')

            # "Okay, here is the report plot. You can click [here]({report_url}) to view the interactive report."
            message = dict()
            message['text'] = "Okay, here is the report plot."
            message['custom'] = {}
            if preview_image_url:
                message['image'] = preview_image_url
            if interactive_plot:
                message['custom']['chart'] = interactive_plot

            dispatcher.utter_message(**message)
            dispatcher.utter_message(response="utter_did_that_help")
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
            dispatcher.utter_message(text="Found %d sensor(s):" % len(sensors))
            sensorlist_msg: str = ""
            for sensor in sensors:
                sensor_name = integration_genesis.sensor_name_coalesce(sensor)
                sensor_location = integration_genesis.location_name_coalesce(sensor["sensor_location"])
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
        LOGGER.info("Running action_search_sensor_by_name")
        sensor_name: Optional[str] = tracker.get_slot("sensor_name")
        LOGGER.info("slot sensor_name filled with %s", sensor_name)
        try:
            sensor = await integration_genesis.determine_user_request_sensor(
                sensor_name=sensor_name,  # TODO: Get from slot
            )
            reset_slot(slot_name="metric", value=sensor["sensor_type"], events=events)
            reset_slot(slot_name="location", value=sensor["sensor_location"]['unit_alias'], events=events)
            # TODO: [NARAYAN] Improve grammar, make it shorter, show only sensor name and not dict.
            dispatcher.utter_message(text=f"found sensor as to be : {sensor}")
        except HTTPStatusError as exc:
            if exc.response.is_client_error:
                raise ClientException("Requested data does not exist.")
        except ConnectError as e:
            raise ServerException("Couldn't connect to Abot backend.", e)
        except Exception as e:  # TODO: Capture specific exceptions
            raise ServerException("Something went wrong while looking up sensor data.", e)
        return events


class ActionResetSlot(Action):
    def name(self):
        return "action_reset_slot"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []
        reset_slot(slot_name="sensor_name",value=None, events=events)
        reset_slot(slot_name="metric",value=None, events=events)
        reset_slot(slot_name="location",value=None, events=events)
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
