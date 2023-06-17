
import logging

from rasa_sdk import Action
from rasa_sdk import utils as ra_utils
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict
from rasa_sdk import events as ra_ev
from rasa_sdk.events import EventType

from .actions_sensor import search_best_matching_sensors
from .common import ClientException
from .api.integration_genesis.schemas import SensorMetadata, LocationMetadata
from .api import (HTTPStatusError, FulfillmentContext, integration_genesis)

from typing import Any, Dict, List, Text


LOGGER = logging.getLogger(__name__)


class ValidateSensorNameForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_form_sensor_name"

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
            return [ra_ev.ActiveLoop(None), ra_ev.UserUtteranceReverted()]

        if slot_value[:1] == '$':
            sensor_id: int = int(slot_value.split('$',1)[-1])

            params: Dict = tracker.slots.get('sensor_load_params') or {}

            with FulfillmentContext(tracker):
                sensor: SensorMetadata = await integration_genesis.sensor_query_metadata(sensor_id)
                params.update({
                    "sensor_id": sensor['sensor_id']
                })
                return [
                    ra_ev.SlotSet("sensor_name", sensor["sensor_urn"]),
                    ra_ev.SlotSet("flag_should_ask_sensor_name", True),
                    ra_ev.SlotSet("sensor_load_params", params)
                ]


        def loc_at_str(s):
            if s:
                return ' at ' + s
            return ''

        try:
            search_sensors = await search_best_matching_sensors(tracker, {
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
            loader_params = tracker.slots.get('sensor_load_params') or {}
            loader_params.update({
                "sensor_id": search_sensors[0]['sensor_id']
            })
            return {
                "sensor_name": slot_value,
                "sensor_load_params": loader_params,
                "flag_should_ask_sensor_name": True,
                "flag_require_new_sensor_input": False
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
                for sensor_obj in search_sensors[:5]
            ])

            return {"sensor_name": None, "flag_should_ask_sensor_name": False}


class ActionAskForSensorNameSlot(Action):
    def name(self) -> Text:
        return "action_ask_sensor_name"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        if tracker.get_slot('flag_should_ask_sensor_name'):
            dispatcher.utter_message(text="Enter the sensor name:")
        return []
