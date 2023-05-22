
import asyncio
import json
from typing import Any, Dict, List, Optional

import pandas as pd
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from .api import statapi
from .api.dataapi import get_loaded_data
from .common import (ACTION_STATEMENT_CONTEXT_SLOT, ClientException,
                     action_exception_handle_graceful)
from .insights import describe_all_data_insights
from .language_helper import user_to_aggregation_type
from .schemas import StatementContext
from .language_helper import summary_AggregationOut


class ActionAggregation(Action):
    def name(self):
        return 'action_aggregation'

    @action_exception_handle_graceful
    async def run(self, dispatcher: "CollectingDispatcher", tracker: Tracker, domain: "DomainDict") -> List[Dict[str, Any]]:
        events = []
        user_req_agg_method: Optional[str] = tracker.get_slot("aggregation")
        # Check aggregation method provided by the user
        aggregation = user_to_aggregation_type(user_req_agg_method)

        # TODO: Needs overhaul, this was done in a rush
        data_raw = await get_loaded_data(tracker)
        if data_raw is None:
            raise ClientException("No data is loaded to perform %s aggregation.\nTry loading sensor data." %
                                  aggregation.value, print_traceback=False)

        if data_raw['content'] is None:
            dispatcher.utter_message("Sorry, data isn't available.")
        else:
            data_df: pd.DataFrame = data_raw['content']['data']
            data_meta = data_raw['content']['metadata']
            if data_df.empty:
                dispatcher.utter_message("Sorry, data isn't available for the time range.")
            else:
                aggregated_result = await statapi.aggregation(data_df, aggregation)
                agg_response_text = summary_AggregationOut(aggregated_result, unit_symbol=data_meta["display_unit"])
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
        if action_performed == 'action_metric_aggregate':
            ex_data: str = bot_prev_statement_ctx.get("extra_data")
            extra_data: dict = json.loads(ex_data)
            if extra_data['operation'] == 'aggregation':
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
        if action_performed == 'action_metric_aggregate':
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
