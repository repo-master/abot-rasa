
import asyncio
import json
from typing import Any, Dict, List, Optional

import pandas as pd
from rasa_sdk import Action, Tracker
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from .api import statapi
from .api.dataapi import get_loaded_data
from .api.cache import PandasDataCache
from .api.statapi.schemas import AggregationMethod

from .common import (ACTION_STATEMENT_CONTEXT_SLOT, ClientException, JSONCustomEncoder,
                     action_exception_handle_graceful, find_event_first)
from .insights import describe_all_data_insights
from .language_helper import user_to_aggregation_type
from .schemas import StatementContext
from .language_helper import summary_AggregationOut


def cast_float(o, default = None) -> Optional[float]:
    try:
        if o == float('inf') or o == float('-inf'):
            return default
        return float(o)
    except (TypeError, ValueError):
        return default


def update_statement_context(tracker: Tracker, events: list, data: StatementContext):
    curr_val = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT, {})
    if curr_val is None:
        curr_val = {}
    curr_val.update(data)
    ev = [SlotSet(ACTION_STATEMENT_CONTEXT_SLOT, curr_val)]
    tracker.add_slots(ev)
    events.extend(ev)


class ActionAggregation(Action):
    def name(self):
        return 'action_aggregation'

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[str, Any]]:
        events = []
        analysis_events = []
        user_req_agg_method: Optional[str] = tracker.get_slot("aggregation")
        # Check aggregation method provided by the user
        aggregation = user_to_aggregation_type(user_req_agg_method)

        # print("Events", tracker.events)

        # TODO: Needs overhaul, this was done in a rush
        data_raw: PandasDataCache = await get_loaded_data(tracker, analysis_events)
        if data_raw is None:
            raise ClientException("No data is loaded to perform %s aggregation.\nTry loading sensor data." %
                                  aggregation.value, print_traceback=False)
        data_df: pd.DataFrame = data_raw.df
        data_meta: dict = data_raw.metadata
        if data_df.empty:
            dispatcher.utter_message("Sorry, data isn't available for the time range.")
        else:
            analysis_result = find_event_first("data_analysis_done", analysis_events)
            if analysis_result:
                update_statement_context(tracker, events, {
                    "intent_used": tracker.latest_message.get('intent'),
                    "action_performed": self.name(),
                    "extra_data": json.dumps({
                        "insights": analysis_result['insights'],
                        "counts": analysis_result['counts']
                    }, cls=JSONCustomEncoder)
                })

                insight_type_counts: dict = analysis_result['counts']
                if len(insight_type_counts) > 0:
                    counts = '\n'.join([
                        "- %d %s(s)" % (v, k) for k, v in insight_type_counts.items()
                    ])
                    dispatcher.utter_message(text="In the selected data, I've found:\n%s" % counts)

            agg_opts = {}

            # Special cases
            if aggregation == AggregationMethod.QUANTILE:
                if not tracker.get_slot("quantile"):
                    # If percentile slot is not filled, ask the user for the value
                    dispatcher.utter_message("What value of percentile?")
                    return events
                # Percentile (between 0.0 and 1.0)
                agg_opts.update({"quantile_size": cast_float(tracker.get_slot("quantile"), 50) / 100.0})

            # Special cases
            if aggregation == AggregationMethod.COMPLIANCE:
                if not (tracker.get_slot("compliance_bound_lower") or tracker.get_slot("compliance_bound_upper")):
                    dispatcher.utter_message("What lower and/or upper target?")
                    return events

                agg_opts.update({
                    "lower_target": cast_float(tracker.get_slot("compliance_bound_lower")),
                    "upper_target": cast_float(tracker.get_slot("compliance_bound_upper"))
                })

            aggregated_result = await statapi.aggregation(data_df, aggregation, **agg_opts)
            agg_response_text = summary_AggregationOut(aggregated_result, unit_symbol=data_meta.get("display_unit", ''), **agg_opts)
            dispatcher.utter_message(agg_response_text)

        return events


class ActionDescribeEventDetails(Action):
    def name(self):
        return "action_describe_event_details"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        bot_prev_statement_ctx: Optional[StatementContext] = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT)
        if bot_prev_statement_ctx is None:
            dispatcher.utter_message(text="Don't know what to describe.")
            return []

        # agg_used = user_to_aggregation_type(user_req_agg_method)

        action_performed = bot_prev_statement_ctx.get("action_performed")
        if action_performed == 'action_aggregation':
            ex_data: str = bot_prev_statement_ctx.get("extra_data")
            extra_data: dict = json.loads(ex_data)
            discovered_insights: list = extra_data.get("insights", [])
            # Generate description of aggregation insights and send
            messages = describe_all_data_insights(discovered_insights)
            list(map(lambda msg: dispatcher.utter_message(**msg), messages))

        return events


class ActionDescribeCountEventDetails(Action):
    def name(self):
        return "action_describe_outlier_count"

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        bot_prev_statement_ctx: Optional[StatementContext] = tracker.slots.get(ACTION_STATEMENT_CONTEXT_SLOT)
        if bot_prev_statement_ctx is None:
            dispatcher.utter_message(text="Don't know what to describe.")
            return []

        # agg_used = user_to_aggregation_type(user_req_agg_method)

        action_performed = bot_prev_statement_ctx.get("action_performed")
        if action_performed == 'action_aggregation':
            ex_data: str = bot_prev_statement_ctx.get("extra_data")
            extra_data: dict = json.loads(ex_data)

            try:
                df = pd.DataFrame(extra_data['insights'])
                # expand the data_point dictionary into separate columns
                df = pd.concat([df.drop(['data_point'], axis=1), df['data_point'].apply(pd.Series)], axis=1)
                df = df[df['type'] == 'outlier']
                count_value = df['value'].count()

                dispatcher.utter_message(text=f"there where {count_value} extreme case(s)")
            except KeyError:
                dispatcher.utter_message(text=f"No Outlier found")

        return events


class ActionAskForSensorNameSlot(Action):
    def name(self) -> str:
        return "action_ask_quantile"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        dispatcher.utter_message(text="Enter the percentile (eg. 99):")
        return []

class ValidateAggregationComplianceForm(FormValidationAction):
    def name(self) -> str:
        return "validate_form_aggregation_compliance"

    # Slot validation
    # - compliance_bound_lower
    # - compliance_bound_upper

    def validate_compliance_bound_lower(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> EventType:
        if not tracker.active_loop.get('name'):
            return {}
        if str(slot_value).lower() == 'none':
            return {"compliance_bound_lower": float('-inf')}
        try:
            return {"compliance_bound_lower": float(slot_value)}
        except (TypeError, ValueError):
            dispatcher.utter_message(text="Invalid value. Enter a number or 'none'.")
            return {"compliance_bound_lower": None}

    def validate_compliance_bound_upper(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> EventType:
        if not tracker.active_loop.get('name'):
            return {}
        if str(slot_value).lower() == 'none':
            return {"compliance_bound_upper": float('inf')}
        try:
            return {"compliance_bound_upper": float(slot_value)}
        except (TypeError, ValueError):
            dispatcher.utter_message(text="Invalid value. Enter a number or 'none'.")
            return {"compliance_bound_upper": None}


class ActionResetQuantileSlot(Action):
    def name(self) -> str:
        return "action_reset_quantile_slot_set_agg_type"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        print("Quantile:", tracker.get_slot('quantile'))
        print("Entity set:", tracker.latest_message)

        return [
            SlotSet("aggregation", [AggregationMethod.QUANTILE])
        ]


class ActionResetComplianceSlot(Action):
    def name(self) -> str:
        return "action_reset_compliance_slot_set_agg_type"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        print("Compliance: Lower:", tracker.get_slot('compliance_bound_lower'), "Upper:", tracker.get_slot('compliance_bound_upper'))
        print("Entity set:", tracker.latest_message)

        return [
            SlotSet("aggregation", [AggregationMethod.COMPLIANCE])
        ]

