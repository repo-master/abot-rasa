# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Text, Union

import humanize
import pandas as pd
from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.events import (FollowupAction, ConversationPaused,
                             SlotSet, UserUtteranceReverted)
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from .api import HTTPStatusError, ConnectError
from .api.aggregation import (AggregationMethod, SensorMetadata, TimeRange,
                              TimeRangeIn, determine_user_request_sensor,
                              get_outliner, get_report_generate_preview,
                              get_sensor_data, perform_aggregation_on_data,
                              user_to_aggregation_type, user_to_sensor_type,
                              user_to_timeperiod, query_sensor_list, sensor_name_coalesce,
                              unit_name_coalesce)
from .insights import describe_all_data_insights
from .schema import StatementContext

LOG = logging.getLogger(__name__)
ACTION_STATEMENT_CONTEXT_SLOT = "statement_context"


class JSONCustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (pd.DataFrame, pd.Series)):
            return o.to_dict()
        if isinstance(o, pd.Timestamp):
            return o.isoformat()
        LOG.warning("Custom JSON encoder couldn't encode %s.", str(type(o)))
        return super().default(o)


def update_statement_context(tracker: Tracker, events: list, data: StatementContext):
    curr_val = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT, {})
    if curr_val is None:
        curr_val = {}
    curr_val.update(data)
    ev = [SlotSet(ACTION_STATEMENT_CONTEXT_SLOT, curr_val)]
    tracker.add_slots(ev)
    events.extend(ev)


class ServerException(Exception):
    def __init__(self, msg, original_exc):
        super().__init__(msg)
        self._msg = msg
        self.exc = original_exc

    def __str__(self):
        return "Woops! {msg}\nPlease try again after some time.\nError reason: \"{reason}\"".format(
            msg=self._msg,
            reason="%s: %s" % (type(self.exc).__name__, str(self.exc))
        )


class ClientException(Exception):
    pass


def action_exception_handle_graceful(fn: Callable[[CollectingDispatcher, Tracker, DomainDict], List[Dict[str, Any]]]):
    async def _wrapper_fn(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[str, Any]]:
        try:
            return await fn(self, dispatcher, tracker, domain)
        except ClientException as exc:
            dispatcher.utter_message(str(exc))
            return []
        # Add any specific exceptions here to send response to that need a different response.
        except Exception as exc:
            LOG.exception("Unhandled exception:", exc_info=exc)
            LOG.info("[for above exception] Current state:\n%s", str(tracker.current_state()))

            # Send exception to user. If it is `ServerException` the message will be more user-friendly.
            if not isinstance(exc, ServerException):
                # wrap exception into `ServerException`
                exc = ServerException("Something went wrong while performing your request.", exc)
            dispatcher.utter_message(text=str(exc))
            # No events are sent since it failed
            return []
    return _wrapper_fn


async def parse_input_sensor_operation(dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict, events: List[Dict[Text, Any]]) -> Dict:
    user_input = {}

    # We need these slots
    user_req_metric: Optional[str] = tracker.get_slot("metric")
    user_req_location: Optional[str] = tracker.get_slot("location")
    user_req_agg_method: Optional[str] = tracker.get_slot("aggregation")
    user_req_timeperiod: Optional[TimeRangeIn] = tracker.get_slot("timestamp_agg_period")

    user_input.update({
        'user_req_metric': user_req_metric,
        'user_req_location': user_req_location,
        'user_req_agg_method': user_req_agg_method,
        'user_req_timeperiod': user_req_timeperiod
    })

    # Debug output
    print("Got slots: Metric: %s, Location: %s, Aggregation: %s, timestamp_agg_period: %s" % (
        user_req_metric, user_req_location, user_req_agg_method, str(user_req_timeperiod)))

    # Check aggregation method provided by the user
    user_input['aggregation'] = user_to_aggregation_type(user_req_agg_method)

    user_input['timeperiod'] = user_to_timeperiod(tracker, events)
    if user_input['timeperiod'] is None:
        raise ClientException("Need to know for what time period to load the data.")

    print("Aggregation time range:", tracker.slots.get("timestamp_agg_timerange"))

    # TODO: More assumption magic needed

    # Either one can be set
    try:
        user_input['sensor'] = await determine_user_request_sensor(
            sensor_type=user_req_metric,
            sensor_name=None,  # TODO: Get from slot
            location=user_req_location
        )
    except HTTPStatusError as exc:
        if exc.response.is_client_error:
            raise ClientException("Requested data does not exist.")
    except ConnectError as e:
        raise ServerException("Couldn't connect to Abot backend.", e)
    except Exception as e:  # TODO: Capture specific exceptions
        raise ServerException("Something went wrong while looking up sensor data.", e)

    return user_input


def exit_reject_sensor_data_incorrect(
        action_name: str,
        dispatcher: CollectingDispatcher,
        events: List,
        data: Dict[str, str],
        message: str = None):

    if message is None:
        message = "The sensor {user_req_metric} does not exist at location \"{user_req_location}\". Please enter proper data for the same"

    dispatcher.utter_message(text=message.format(**data))

    # HACK: Had to disable this due to above message dispatch
    # events.extend([ActionExecutionRejected(action_name)])

    return events


class ActionMetricAggregate(Action):
    def name(self):
        return "action_metric_aggregate"

    @action_exception_handle_graceful
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []
        user_input = await parse_input_sensor_operation(dispatcher, tracker, domain, events)

        # Any special things found with the data for further analysis
        data_insights = []

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
        response_data = await get_sensor_data(requested_sensor_id, requested_timeperiod["from"], requested_timeperiod["to"])

        # TODO: Run checks on above

        if response_data is not None:
            data, metadata = response_data
            # Run aggregation
            aggregated_result = perform_aggregation_on_data(data, aggregation, metadata)

            if aggregated_result:
                response_string: str = aggregated_result.pop('result_format', '')
                # Generate response sentence
                fmt_options = {
                    # Add any other options here to pass to the below format string
                    **aggregated_result
                }

                response_text = response_string.format(**fmt_options)

                # Say the sentence
                dispatcher.utter_message(response_text)

                aggregation_followup_response_buttons: List[Dict[str, str]] = [
                    {"title": "Min", "payload": "minimum"},
                    {"title": "Max", "payload": "maximum"},
                    {"title": "Average", "payload": "average"},
                    {"title": "Current", "payload": "current"}
                ]

                outliers = get_outliner(data, metadata)
                if not outliers.empty:
                    # df_outlier = pd.DataFrame(list(outliers.items()), columns=['timestamp', 'value'])

                    dispatcher.utter_message(
                        f"Discovered {outliers['value'].count()} outlier value(s) within the data.")
                    # dispatcher.utter_message(f"Minimum value of outlier is {outliers['value'].min()} at {outliers.loc[outliers['value'].idxmin(), 'timestamp']}")
                    # dispatcher.utter_message(f"Maximum value of outlier is {outliers['value'].max()}")

                    aggregation_followup_response_buttons.append({
                        "title": "Outlier details",
                        "payload": "describe the outlier"
                    })

                    for outlier_idx, outlier_ser in outliers.iterrows():
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
            else:
                dispatcher.utter_message("Sorry, data for {sensor_type} isn't available for the time range.".format(
                    sensor_type=metadata['sensor_type']
                ))

        else:
            dispatcher.utter_message("Sorry, data for {sensor_req} isn't available.".format(
                sensor_req=user_input.get('user_req_metric')
            ))

        return events


class ActionFetchReport(Action):
    def name(self) -> Text:
        return "action_fetch_report"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []
        user_input = await parse_input_sensor_operation(dispatcher, tracker, domain, events)

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
        try:
            report_data: dict = await get_report_generate_preview(requested_sensor_id, requested_timeperiod["from"], requested_timeperiod["to"])

            report_url: str = report_data['interactive_report_route']
            preview_image_url: str = report_data['preview_image']

            dispatcher.utter_message(
                text="Okay, here is the report plot. You can click [here]({report_url}) to view the interactive report.".format(
                    report_url=report_url
                ),
                image=preview_image_url
            )
            events.append(FollowupAction("utter_did_that_help"))
        except HTTPStatusError as exc:
            if exc.response.is_client_error:
                raise ClientException(
                    "Sorry, there isn't any data present for the given sensor at the given time range.")

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


class ActionDescribeEventDetails(Action):
    def name(self):
        return "action_describe_event_details"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []

        bot_prev_statement_ctx: Optional[StatementContext] = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT)
        if bot_prev_statement_ctx is None:
            dispatcher.utter_message(text="Don't know what to describe.")
            return []

        # agg_used = user_to_aggregation_type(user_req_agg_method)

        action_performed = bot_prev_statement_ctx.get("action_performed")
        if action_performed == 'action_metric_aggregate':
            ex_data: str = bot_prev_statement_ctx.get("extra_data")
            extra_data: dict = json.loads(ex_data)
            if extra_data['operation'] == 'aggregation':
                discovered_insights: list = extra_data.get("insights", [])
                # Generate description of aggregation insights and send
                messages = describe_all_data_insights(discovered_insights)
                list(map(lambda msg: dispatcher.utter_message(**msg), messages))

        return events


class ActionDescribeMinEventDetails(Action):
    def name(self):
        return "action_describe_min_event"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []

        bot_prev_statement_ctx: Optional[StatementContext] = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT)
        if bot_prev_statement_ctx is None:
            dispatcher.utter_message(text="Don't know what to describe.")
            return []

        # agg_used = user_to_aggregation_type(user_req_agg_method)

        action_performed = bot_prev_statement_ctx.get("action_performed")
        if action_performed == 'action_metric_aggregate':
            ex_data: str = bot_prev_statement_ctx.get("extra_data")
            extra_data: dict = json.loads(ex_data)

            df = pd.DataFrame(extra_data['insights'])
            # expand the data_point dictionary into separate columns
            df = pd.concat([df.drop(['data_point'], axis=1), df['data_point'].apply(pd.Series)], axis=1)
            df = df[df['type'] == 'outlier']
            min_value = df['value'].min()

            dispatcher.utter_message(text=f"the minimum value of outlier was found to be {min_value}")
        return events


class ActionDescribeMaxEventDetails(Action):
    def name(self):
        return "action_describe_max_event"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []

        bot_prev_statement_ctx: Optional[StatementContext] = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT)
        if bot_prev_statement_ctx is None:
            dispatcher.utter_message(text="Don't know what to describe.")
            return []

        # agg_used = user_to_aggregation_type(user_req_agg_method)

        action_performed = bot_prev_statement_ctx.get("action_performed")
        if action_performed == 'action_metric_aggregate':
            ex_data: str = bot_prev_statement_ctx.get("extra_data")
            extra_data: dict = json.loads(ex_data)

            df = pd.DataFrame(extra_data['insights'])
            # expand the data_point dictionary into separate columns
            df = pd.concat([df.drop(['data_point'], axis=1), df['data_point'].apply(pd.Series)], axis=1)
            df = df[df['type'] == 'outlier']
            max_value = df['value'].max()

            dispatcher.utter_message(text=f"the maximum value of outlier was found to be {max_value}")
        return events


class ActionDescribeCountEventDetails(Action):
    def name(self):
        return "action_describe_outlier_count"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []

        bot_prev_statement_ctx: Optional[StatementContext] = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT)
        if bot_prev_statement_ctx is None:
            dispatcher.utter_message(text="Don't know what to describe.")
            return []

        # agg_used = user_to_aggregation_type(user_req_agg_method)

        action_performed = bot_prev_statement_ctx.get("action_performed")
        if action_performed == 'action_metric_aggregate':
            ex_data: str = bot_prev_statement_ctx.get("extra_data")
            extra_data: dict = json.loads(ex_data)

            df = pd.DataFrame(extra_data['insights'])
            # expand the data_point dictionary into separate columns
            df = pd.concat([df.drop(['data_point'], axis=1), df['data_point'].apply(pd.Series)], axis=1)
            df = df[df['type'] == 'outlier']
            count_value = df['value'].count()

            dispatcher.utter_message(text=f"there where {count_value} No. of extreme cases")
        return events


class ActionDescribeSummaryEventDetails(Action):
    def name(self):
        return "action_outlier_summary"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        events: List[Dict[str, Any]] = []

        bot_prev_statement_ctx: Optional[StatementContext] = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT)
        if bot_prev_statement_ctx is None:
            dispatcher.utter_message(text="Don't know what to describe.")
            return []

        # agg_used = user_to_aggregation_type(user_req_agg_method)

        action_performed = bot_prev_statement_ctx.get("action_performed")
        if action_performed == 'action_metric_aggregate':
            ex_data: str = bot_prev_statement_ctx.get("extra_data")
            extra_data: dict = json.loads(ex_data)
            dispatcher.utter_message(text="Sure!")

            df = pd.DataFrame(extra_data['insights'])
            # expand the data_point dictionary into separate columns
            df = pd.concat([df.drop(['data_point'], axis=1), df['data_point'].apply(pd.Series)], axis=1)
            df = df[df['type'] == 'outlier']
            count_value = df['value'].count()
            dispatcher.utter_message(text=f"there where {count_value} No. of extreme cases")
            min_value = df['value'].min()
            dispatcher.utter_message(text=f"the minimum value of outlier was found to be {min_value}")
            max_value = df['value'].max()
            dispatcher.utter_message(text=f"the maximum value of outlier was found to be {max_value}")

        return events


class ActionHumanHandoff(Action):
    def name(self) -> Text:
        return "action_human_handoff"

    def run(self, dispatcher, tracker, domain):
        # output a message saying that the conversation will now be
        # continued by a human.

        message = "Let me transfer you to a human..."
        dispatcher.utter_message(text=message)
        # pause tracker, undo last user interaction
        return [ConversationPaused(), UserUtteranceReverted()]


class ActionShowSensorList(Action):
    def name(self):
        return "action_show_sensor_list"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[Text, Any]]:
        try:
            sensors = await query_sensor_list()
        except ConnectError as e:
            raise ServerException("Couldn't connect to Abot backend.", e)

        if len(sensors) == 0:
            dispatcher.utter_message(text="Presently there are no sensors that I can query.")
        else:
            dispatcher.utter_message(text="I found %d sensor(s) that I can query:" % len(sensors))
            sensorlist_msg: str = ""
            for sensor in sensors:
                sensor_name = sensor_name_coalesce(sensor)
                sensor_location = unit_name_coalesce(sensor["sensor_location"])
                sensor_type = sensor["sensor_type"]
                display_unit = sensor["display_unit"]
                sensorlist_msg += f"- {sensor_name} [measures {sensor_type} ({display_unit})] at {sensor_location}\n"
            dispatcher.utter_message(text=sensorlist_msg)

        return []
