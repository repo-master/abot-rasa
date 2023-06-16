# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

import json
import logging
from typing import Any, Dict, List, Optional, Set, Text, Tuple, Union

from rasa_sdk import Action, Tracker
from rasa_sdk import events as ra_ev
from rasa_sdk.events import EventType
from rasa_sdk.events import ActiveLoop, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict

from .api import (ConnectError, HTTPStatusError, FulfillmentContext, dataapi, integration_genesis,
                  statapi)
from .api.duckling import TimeRange
from .api.integration_genesis.schemas import SensorMetadata, LocationMetadata
from .common import (ClientException, ServerException,
                     action_exception_handle_graceful)
from .language_helper import user_to_timeperiod, string_timestamp_to_human, to_datetime

LOGGER = logging.getLogger(__name__)


all_sensor_list: Dict[int, List[SensorMetadata]] = {}


async def parse_input_sensor_operation(tracker: Tracker, events: List[EventType]) -> Tuple[Dict, Dict]:
    user_input = {}
    parsed_input = {}

    # We need these slots
    user_req_metric: Optional[str] = tracker.get_slot("metric")
    user_req_location: Optional[str] = tracker.get_slot("location")
    user_req_sensor_name: Optional[str] = tracker.get_slot("sensor_name")
    user_req_agg_interval: Optional[str] = tracker.get_slot("load_aggregation_interval")

    user_input.update({
        'user_req_metric': user_req_metric,
        'user_req_location': user_req_location,
        'user_req_sensor_name': user_req_sensor_name,
        'user_req_agg_interval': user_req_agg_interval
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

from fuzzywuzzy import process

def sensor_data_condenser(data: Union[str, SensorMetadata], force_ascii: bool = False) -> str:
    if isinstance(data, str):
        return data
    elif isinstance(data, dict):
        return integration_genesis.sensor_name_coalesce(data) + '_' + data["sensor_type"]
    return ''

def merge_sensor_match_results(*results: List[Tuple[SensorMetadata, int]]) -> List[SensorMetadata]:
    all_results: List[SensorMetadata] = []
    for result in results:
        for sensor, score in result:
            for s_r in all_results:
                if sensor['sensor_id'] == s_r["sensor_id"]:
                    break
            else:
                all_results.append(sensor)
    return all_results

async def search_best_matching_sensors(tracker: Tracker, parsed_input: dict) -> Optional[List[SensorMetadata]]:
    try:
        needs_update = False # TODO
        score_cutoff = 25

        with FulfillmentContext(tracker) as f_id:
            if f_id not in all_sensor_list or needs_update:
                all_sensor_list[f_id] = await integration_genesis.query_sensor_list()
            return merge_sensor_match_results(
                process.extractBests(
                    parsed_input.get('sensor_name', ''),
                    all_sensor_list[f_id],
                    processor=sensor_data_condenser,
                    score_cutoff=score_cutoff),
                process.extractBests(
                    ' '.join([parsed_input.get('sensor_type', ''), parsed_input.get('sensor_location', '')]),
                    all_sensor_list[f_id],
                    processor=sensor_data_condenser,
                    score_cutoff=score_cutoff)
            )
    except HTTPStatusError as exc:
        if exc.response.is_client_error:
            resp = exc.response.json()
            if parsed_input.get('sensor_type'):
                raise ClientException("No sensors of type {sensor_type} present{loc_opt}.".format(
                    sensor_type=parsed_input.get('sensor_type') or parsed_input.get('sensor_name') or 'unknown',
                    loc_opt='' if parsed_input['sensor_location'] is None else ' at %s' % parsed_input['sensor_location']
                ), print_traceback=False)
            elif parsed_input.get('sensor_name'):
                raise ClientException("Sensor named '{sensor_name}' not found.".format(
                    sensor_name=parsed_input['sensor_name']
                ), print_traceback=False)
            elif 'detail' in resp.keys():
                raise ClientException(resp['detail'], print_traceback=False)
    except ConnectError as e:
        raise ServerException("Couldn't connect to Abot backend.", e)
    except ClientException as e:
        raise e
    except Exception as e:  # TODO: Capture specific exceptions
        raise ServerException("Something went wrong while looking up sensor data.", e)

def find_lod(list_of_dict, key, value):
    return next(x for x in list_of_dict if x[key] == value)

class ActionSensorDataLoad(Action):
    '''Loads sensor data with requested parameters'''

    def name(self):
        return "action_sensor_data_load"

    @action_exception_handle_graceful
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        events: List[EventType] = []
        requested_sensor: SensorMetadata = None
        timeperiod: TimeRange = {}
        # parsed_input, user_input = await parse_input_sensor_operation(tracker, events)

        requested_sensor_params: Dict = tracker.slots.get('sensor_load_params') or {}

        if requested_sensor_params.get('sensor_id') is None:
            raise ClientException("No sensor selected.")

        sid_search: int = int(requested_sensor_params.get('sensor_id'))

        with FulfillmentContext(tracker) as f_id:
            if all_sensor_list.get(f_id) is None:
                all_sensor_list[f_id] = await integration_genesis.query_sensor_list()
            requested_sensor = find_lod(all_sensor_list[f_id], 'sensor_id', sid_search)
            timerange_str = requested_sensor_params.get('timeperiod')
            timeperiod = {
                "from": to_datetime(timerange_str['from']),
                "to": to_datetime(timerange_str['to'])
            }

        # dispatcher.utter_message(text="Loading sensor %s at time range %s to %s..." % (
        #     integration_genesis.sensor_name_coalesce(requested_sensor),
        #     parsed_input['timeperiod']['from'].strftime('%c'),
        #     parsed_input['timeperiod']['to'].strftime('%c')
        # ))

        events.append(SlotSet("need_select_sensor", False))

        await dataapi.cached_loader(
            tracker,
            'sensor',
            loader=integration_genesis.get_sensor_data,
            metadata=requested_sensor,
            fetch_range=timeperiod
        )
        events.append(SlotSet("data_source", 'sensor'))

        return events


class ActionFetchReport(Action):
    def name(self) -> Text:
        return "action_fetch_report"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[EventType]:
        events: List[EventType] = []

        try:
            sensor_selected = dataapi.get_cache("sensor")
            if sensor_selected is None:
                raise ClientException(
                    "Sorry, sensor data not selected. Try specifying sensor and time range.",
                    print_traceback=False)
            
            sensor_metadata: SensorMetadata = sensor_selected._loader_params['metadata']
            sensor_data_select_range: TimeRange = sensor_selected._loader_params['fetch_range']
            with FulfillmentContext(tracker):
                report_data: dict = await integration_genesis.get_report_generate_preview(sensor_metadata, sensor_data_select_range)

            preview_image_url: Optional[str] = report_data.get('preview_image')
            interactive_plot: Optional[dict] = report_data.get('plot_interactive')

            # "Okay, here is the report plot. You can click [here]({report_url}) to view the interactive report."
            message = dict()
            message['text'] = "Okay, here is the report plot."
            message['custom'] = {}
            message['buttons'] = []
            if preview_image_url:
                message['image'] = preview_image_url
            if interactive_plot:
                message['custom']['chart'] = interactive_plot
                message['buttons'].append({
                    'title': "Download PDF",
                    'payload': '/sensor_report_download{"download_format": "pdf"}'
                })

            dispatcher.utter_message(**message)
        except HTTPStatusError as exc:
            if exc.response.is_client_error:
                raise ClientException(
                    "Sorry, No data found for sensor at the given time range.")

        return events


class ActionDownloadReport(Action):
    def name(self):
        return "action_download_report"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[EventType]:
        sensor_selected = dataapi.get_cache("sensor")
        if sensor_selected is None:
            raise ClientException(
                "Sorry, sensor data not selected. Try specifying sensor and time range.",
                print_traceback=False)

        sensor_metadata: SensorMetadata = sensor_selected._loader_params['metadata']
        sensor_data_select_range: TimeRange = sensor_selected._loader_params['fetch_range']
        with FulfillmentContext(tracker):
            report_endpoint = integration_genesis.get_report_download_url(sensor_metadata,sensor_data_select_range)
        dispatcher.utter_message(
            text="[Click here](http://uat.phaidelta.com:8091%s) to download the report." % report_endpoint,
            attachment=report_endpoint
        )
        return []


class ActionShowSensorList(Action):
    def name(self):
        return "action_show_sensor_list"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[EventType]:
        try:
            with FulfillmentContext(tracker):
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


class ActionShowLocationList(Action):
    def name(self) -> Text:
        return "action_show_location_list"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        try:
            with FulfillmentContext(tracker):
                locations = await integration_genesis.query_location_list()
        except ConnectError as e:
            raise ServerException("Couldn't connect to Abot backend.", e)

        if len(locations) == 0:
            dispatcher.utter_message(text="No locations available.")
        else:
            dispatcher.utter_message(text="Found %d locations(s):" % len(locations))
            loclist_msg: str = ""
            for loc in locations:
                location_name = integration_genesis.location_name_coalesce(loc)
                loclist_msg += f"- {location_name}\n"
            dispatcher.utter_message(text=loclist_msg)

        return []


class ActionQuerySensorStatus(Action):
    def name(self) -> Text:
        return "action_query_sensor_status"

    @action_exception_handle_graceful
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        try:
            with FulfillmentContext(tracker):
                sensor_selected = dataapi.get_cache("sensor")
                if sensor_selected is None:
                    raise ClientException(
                        "Sorry, sensor data not selected. Try specifying a sensor.",
                        print_traceback=False)
                sensor_metadata_old: SensorMetadata = sensor_selected._loader_params['metadata']
                sensor_metadata_updated = await integration_genesis.sensor_query_metadata(sensor_metadata_old["sensor_id"])
                if not sensor_metadata_updated:
                    raise ClientException("Couldn't get information on sensor %s." %
                                        integration_genesis.sensor_name_coalesce(sensor_metadata_old))

                status_msg = "Information for {sensor_name}:"
                status_msg += "\n- Sensor type: {sensor_type}"
                status_msg += "\n- Health: {sensor_health}"
                status_msg += "\n- Last reading: {sensor_reading}"

                sensor_status_health = "UNKNOWN"
                sensor_last_reading = "UNKNOWN"
                if sensor_metadata_updated['sensor_status']:
                    if sensor_metadata_updated['sensor_status']['sensor_health'] and sensor_metadata_updated['sensor_status']['sensor_health']['code_name']:
                        sensor_status_health = sensor_metadata_updated['sensor_status']['sensor_health']['code_name']

                    if sensor_metadata_updated['sensor_status']['last_value']:
                        # TODO: ['value'] part depends on sensor type (it can be 'state')
                        sensor_last_reading = "%s%s" % (
                            sensor_metadata_updated['sensor_status']['last_value']['value'],
                            sensor_metadata_updated['display_unit']
                        )
                        if sensor_metadata_updated['sensor_status']['last_timestamp']:
                            ts_human = string_timestamp_to_human(sensor_metadata_updated['sensor_status']['last_timestamp'])
                            sensor_last_reading += " (at %s)" % ts_human

                dispatcher.utter_message(text=status_msg.format(
                    sensor_name=integration_genesis.sensor_name_coalesce(sensor_metadata_updated),
                    sensor_type=sensor_metadata_updated['sensor_type'],
                    sensor_health=sensor_status_health,
                    sensor_reading=sensor_last_reading
                ))
        except ConnectError as e:
            raise ServerException("Couldn't connect to Abot backend.", e)

        return []


class ActionShowTimerangeValue(Action):
    def name(self) -> Text:
        return "action_ask_data_value_timerange"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        HUMAN_TIME_FORMAT = "%c"
        time_range = await user_to_timeperiod(tracker, autoset_default=None)
        if time_range:
            dispatcher.utter_message(text="Data time range: *{t_from}* till *{t_to}*".format(
                t_from=time_range["from"].strftime(HUMAN_TIME_FORMAT),
                t_to=time_range["to"].strftime(HUMAN_TIME_FORMAT)
            ))
        else:
            dispatcher.utter_message(text="Time range is not provided for data.")
        return []


class ActionShowLocationValue(Action):
    def name(self) -> Text:
        return "action_ask_data_value_location"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        user_req_location: Optional[str] = tracker.get_slot("location")
        if user_req_location:
            dispatcher.utter_message(text="Location: %s" % user_req_location)
        else:
            dispatcher.utter_message(text="Location is not provided for data.")
        return []


class ActionAskTimeRange(Action):
    def name(self) -> Text:
        return "action_ask_data_time_range"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        dispatcher.utter_message(text="Time range:")
        return []


class ActionSensorLoadSlotSetup(Action):
    def name(self) -> Text:
        return "action_setup_load_slots"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        events: List[EventType] = []
        parsed, user = await parse_input_sensor_operation(tracker, events)
        params: Dict = tracker.slots.get('sensor_load_params') or {}
        params.update({
            "timeperiod": {
                "from": parsed['timeperiod']['from'].isoformat(),
                "to": parsed['timeperiod']['to'].isoformat()
            }
        })
        events.append(SlotSet("sensor_load_params", params))
        events.append(SlotSet("metric", None))
        return events
