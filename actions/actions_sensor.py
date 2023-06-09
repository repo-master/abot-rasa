# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

import json
import logging
from typing import Any, Dict, List, Optional, Text, Tuple, Union

from rasa_sdk import Action, Tracker
from rasa_sdk import events as ra_ev
from rasa_sdk.events import EventType
from rasa_sdk import utils as ra_utils
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.events import ActionReverted, ActiveLoop, ActionExecutionRejected, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict

from .api import (ConnectError, HTTPStatusError, FulfillmentContext, dataapi, integration_genesis,
                  statapi)
from .api.duckling import TimeRange
from .api.integration_genesis.schemas import SensorMetadata
from .common import (ClientException, ServerException,
                     action_exception_handle_graceful)
from .language_helper import user_to_timeperiod, string_timestamp_to_human

LOGGER = logging.getLogger(__name__)


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


def reset_slot(slot_name, value, events: list):
    events.append(SlotSet(slot_name, value))


async def search_best_matching_sensors(parsed_input: dict) -> Optional[List[SensorMetadata]]:
    try:
        # TODO: If sensor id is given, fetch metadata of it directly
        # Either one can be set
        if parsed_input['sensor_name'] is not None:
            return await integration_genesis.determine_user_request_sensor(
                sensor_name=parsed_input['sensor_name']
            )
        else:
            return await integration_genesis.determine_user_request_sensor(
                sensor_type=parsed_input['sensor_type'],
                location=parsed_input['sensor_location']
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
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[EventType]:
        events: List[EventType] = []
        parsed_input, user_input = await parse_input_sensor_operation(tracker, events)

        with FulfillmentContext(tracker):
            requested_sensors = await search_best_matching_sensors(parsed_input)

        requested_sensor: SensorMetadata = None

        if requested_sensors is None:
            dispatcher.utter_message(text="Couldn't search for the given sensor")
            return events
        elif len(requested_sensors) == 1:
            requested_sensor = requested_sensors[0]
        elif len(requested_sensors) > 1:
            def loc_at_str(s):
                if s:
                    return ' at ' + s
                return ''
            dispatcher.utter_message(text="Which sensor? Select one:", buttons=[
                {
                    "title": "%s%s" % (
                        integration_genesis.sensor_name_coalesce(sensor_obj),
                        loc_at_str(integration_genesis.location_name_coalesce(sensor_obj.get('sensor_location')))
                    ),
                    "payload": "/activate_sensor_name_form%s" % (
                        json.dumps({"sensor_name_input": sensor_obj["sensor_urn"]})
                    )
                }
                for sensor_obj in requested_sensors
            ])
            events.append(SlotSet("need_select_sensor", True))
            events.append(ra_ev.UserUtteranceReverted())
            return events

        dispatcher.utter_message(text="Loading sensor %s at time range %s to %s..." % (
            integration_genesis.sensor_name_coalesce(requested_sensor),
            parsed_input['timeperiod']['from'].strftime('%c'),
            parsed_input['timeperiod']['to'].strftime('%c')
        ))

        events.append(SlotSet("need_select_sensor", False))
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


class ActionResetSlot(Action):
    def name(self):
        return "action_reset_slot"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[EventType]:
        events: List[EventType] = []
        reset_slot(slot_name="sensor_name", value=None, events=events)
        reset_slot(slot_name="metric", value=None, events=events)
        reset_slot(slot_name="location", value=None, events=events)
        return events


class ActionResetSensorNameSlot(Action):
    def name(self):
        return "action_reset_sensor_name"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[EventType]:
        return [SlotSet("sensor_name", None)]


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


# Sensor name

class ActionAskForSensorNameSlot(Action):
    def name(self) -> Text:
        return "action_ask_sensor_name"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        if tracker.get_slot('flag_should_ask_sensor_name'):
            dispatcher.utter_message(text="Enter the sensor name:")
        return []

class ValidateSensorForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_form_sensor_name"

    # Override
    async def get_validation_events(
        self,
        dispatcher: "CollectingDispatcher",
        tracker: "Tracker",
        domain: "DomainDict",
    ) -> List[EventType]:
        """Validate slots by calling a validation function for each slot.

        Args:
            dispatcher: the dispatcher which is used to
                send messages back to the user.
            tracker: the conversation tracker for the current user.
            domain: the bot's domain.

        Returns:
            `SlotSet` events for every validated slot.
        """
        slots_to_validate = await self.required_slots(
            self.domain_slots(domain), dispatcher, tracker, domain
        )
        slots: Dict[Text, Any] = tracker.slots_to_validate()

        for slot_name, slot_value in list(slots.items()):
            if slot_name not in slots_to_validate:
                slots.pop(slot_name)
                continue

            method_name = f"validate_{slot_name.replace('-','_')}"
            validate_method = getattr(self, method_name, None)

            if not validate_method:
                LOGGER.warning(
                    f"Skipping validation for `{slot_name}`: there is no validation "
                    f"method specified."
                )
                continue

            validation_output = await ra_utils.call_potential_coroutine(
                validate_method(slot_value, dispatcher, tracker, domain)
            )

            events = []

            if isinstance(validation_output, dict):
                if validation_output.get('event'):
                    events.append(validation_output)
                    tracker.events.append(validation_output)
                else:
                    slots.update(validation_output)
                    # for sequential consistency, also update tracker
                    # to make changes visible to subsequent validate_{slot_name}
                    tracker.slots.update(validation_output)
            elif isinstance(validation_output, list):
                events.extend(validation_output)
                tracker.events.extend(validation_output)

        events.extend([SlotSet(*s) for s in slots.items()])

        return events


    # Slot validation
    async def validate_sensor_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> EventType:
        if not tracker.active_loop.get('name'):
            return {"flag_should_ask_sensor_name": True}

        if slot_value == 'exit':
            return [ActiveLoop(None), ra_ev.UserUtteranceReverted()]

        def loc_at_str(s):
            if s:
                return ' at ' + s
            return ''

        with FulfillmentContext(tracker):
            try:
                search_sensors = await search_best_matching_sensors({
                    'sensor_name': slot_value
                })
                if search_sensors is None:
                    search_sensors = []
            except (HTTPStatusError, ClientException):
                search_sensors = []

        if len(search_sensors) == 0:
            # No matches
            dispatcher.utter_message(text="Sensor named '%s' not found." % slot_value)
            return {"sensor_name": None, "flag_should_ask_sensor_name": True}
        elif len(search_sensors) == 1:
            # Match found
            return {
                "sensor_name": slot_value,
                "location": None,
                "metric": None,
                "flag_should_ask_sensor_name": True
            }
        else:
            # More than 1
            dispatcher.utter_message(text="Select a sensor from matches:", buttons=[
                {
                    "title": "%s%s" % (
                        integration_genesis.sensor_name_coalesce(sensor_obj),
                        loc_at_str(integration_genesis.location_name_coalesce(sensor_obj.get('sensor_location')))
                    ),
                    "payload": sensor_obj["sensor_name"]
                }
                for sensor_obj in search_sensors
            ])

            return {"sensor_name": None, "flag_should_ask_sensor_name": False}

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: "CollectingDispatcher",
        tracker: "Tracker",
        domain: "DomainDict",
    ) -> List[Text]:
        text_of_last_user_message = tracker.latest_message.get("text")
        updated_slots = domain_slots.copy()
        return updated_slots
