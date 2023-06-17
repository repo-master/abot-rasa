
import logging

from rasa_sdk import Action
from rasa_sdk import utils as ra_utils
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict
from rasa_sdk import events as ra_ev
from rasa_sdk.events import EventType

from .actions_sensor import search_best_matching_sensors, locations_containing_sensor_type

from .common import ClientException
from .api.integration_genesis.schemas import SensorMetadata, LocationMetadata
from .api import (HTTPStatusError, FulfillmentContext, integration_genesis)

from typing import Any, Dict, List, Text


LOGGER = logging.getLogger(__name__)


class ValidateSensorTypeForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_form_sensor_type_location"

    # Override
    async def get_validation_events(
        self,
        dispatcher: "CollectingDispatcher",
        tracker: "Tracker",
        domain: "DomainDict",
    ) -> List[EventType]:
        slots_to_validate = await self.required_slots(
            self.domain_slots(domain), dispatcher, tracker, domain
        )
        slots: Dict[Text, Any] = tracker.slots_to_validate()
        events = []

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

        events.extend([ra_ev.SlotSet(*s) for s in slots.items()])

        return events

    # Slot validation
    async def validate_location(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> EventType:
        if not tracker.active_loop.get('name'):
            return [ra_ev.SlotSet("flag_should_ask_sensor_location", True)]

        if slot_value == 'exit':
            return [ra_ev.ActiveLoop(None), ra_ev.UserUtteranceReverted(), ra_ev.SlotSet("flag_should_ask_sensor_location", True)]

        if not tracker.slots.get('flag_require_new_sensor_input', False):
            return []

        if slot_value[:1] == '$':
            sensor_id: int = int(slot_value.split('$',1)[-1])

            params: Dict = tracker.slots.get('sensor_load_params') or {}

            with FulfillmentContext(tracker):
                sensor: SensorMetadata = await integration_genesis.sensor_query_metadata(sensor_id)
                params.update({
                    "sensor_id": sensor['sensor_id']
                })
                return [
                    ra_ev.SlotSet("location", sensor['sensor_location']["unit_urn"]),
                    ra_ev.SlotSet("flag_should_ask_sensor_location", True),
                    ra_ev.SlotSet("sensor_load_params", params)
                ]

        def loc_at_str(s):
            if s:
                return ' at ' + s
            return ''

        try:
            search_sensors = await search_best_matching_sensors(tracker, {
                'sensor_type': tracker.slots.get('metric'),
                'sensor_location': slot_value
            })
            if search_sensors is None:
                search_sensors = []
        except (HTTPStatusError, ClientException):
            search_sensors = []

        if len(search_sensors) == 0:
            # No matches
            dispatcher.utter_message(text="Sensor named '%s' not found." % slot_value)
            return {"location": None, "flag_should_ask_sensor_location": True}
        elif len(search_sensors) == 1:
            # Match found
            return {
                "location": slot_value,
                "flag_should_ask_sensor_location": True
            }
        else:
            # More than 1
            dispatcher.utter_message(text="Select a sensor from matches:", buttons=[
                {
                    "title": "%s%s" % (
                        integration_genesis.sensor_name_coalesce(sensor_obj),
                        loc_at_str(integration_genesis.location_name_coalesce(sensor_obj.get('sensor_location')))
                    ),
                    "payload": "$%d" % sensor_obj['sensor_id']
                }
                for sensor_obj in search_sensors
            ])

            return {"location": None, "flag_should_ask_sensor_location": False}


    async def validate_metric(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> EventType:
        if not tracker.active_loop.get('name'):
            return [ra_ev.SlotSet("flag_should_ask_sensor_name", True)]

        if slot_value == 'exit':
            return [ra_ev.ActiveLoop(None), ra_ev.UserUtteranceReverted(), ra_ev.SlotSet("flag_should_ask_sensor_name", True)]

        if not tracker.slots.get('flag_require_new_sensor_input', False):
            return []

        if slot_value[:1] == '$':
            sensor_id: int = int(slot_value.split('$',1)[-1])

            params: Dict = tracker.slots.get('sensor_load_params') or {}

            with FulfillmentContext(tracker):
                sensor: SensorMetadata = await integration_genesis.sensor_query_metadata(sensor_id)
                params.update({
                    "sensor_id": sensor['sensor_id']
                })
                return [
                    ra_ev.SlotSet("metric", sensor["sensor_type"]),
                    ra_ev.SlotSet("flag_should_ask_sensor_name", True),
                    ra_ev.SlotSet("sensor_load_params", params)
                ]

        try:
            search_sensors = await search_best_matching_sensors(tracker, {
                'sensor_type': slot_value
            })
            if search_sensors is None:
                search_sensors = []
        except (HTTPStatusError, ClientException):
            search_sensors = []

        if len(search_sensors) == 0:
            # No matches
            dispatcher.utter_message(text="Sensor of '%s' not found." % slot_value)
            return {"metric": None, "flag_should_ask_sensor_name": True}
        elif len(search_sensors) == 1:
            # Match found
            return {
                "metric": slot_value,
                "flag_should_ask_sensor_name": True,
                "flag_require_new_sensor_input": False
            }
        else:
            # Multiple matches. Force ask location
            return {
                "metric": slot_value,
                "location": None,
                "flag_should_ask_sensor_name": True
            }


class ActionAskForSensorTypeSlot(Action):
    def name(self) -> str:
        return "action_ask_metric"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        if tracker.get_slot('flag_should_ask_sensor_name'):
            dispatcher.utter_message(text="Enter the sensor type:")
        return []

async def get_loc_list(tracker: Tracker, metric_type: str = None) -> List[LocationMetadata]:
    with FulfillmentContext(tracker):
        locs = await integration_genesis.query_location_list()
        if metric_type:
            return locations_containing_sensor_type(tracker, locs, metric_type)
        return locs

class ActionAskForSensorLocationSlot(Action):
    def name(self) -> str:
        return "action_ask_location"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        metric_type = tracker.get_slot('metric')
        if tracker.get_slot('flag_should_ask_sensor_location'):
            locs = await get_loc_list(tracker, metric_type)
            dispatcher.utter_message(text="Enter the sensor's location:", buttons=[
                {
                    "title": integration_genesis.location_name_coalesce(k),
                    "payload": k["unit_urn"]
                }
                for k in locs])
        return []
