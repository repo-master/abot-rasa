# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from random import randint

from rasa_sdk.types import DomainDict
from typing import Any, Text, Dict, List, Union

class ActionCheckTemprature(Action):
    def name(self):
        return "action_check_temprature"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain : DomainDict) -> List[Dict[Text, Any]]:
        return []

class ActionTest(Action):
    def name(self):
        return "action_reply_query"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain : DomainDict) -> List[Dict[Text, Any]]:
        metric = tracker.get_slot("metric")
        room = tracker.get_slot("room")
        aggri = tracker.get_slot("aggregation")
        if 'temp' in metric:
            hard_value = f"{randint(20,30)}'C"
        else:
            hard_value = f"{randint(60,80)}%"
        if aggri is None:
            dispatcher.utter_message(f"{metric} for {room} is {hard_value}")
        else:
            dispatcher.utter_message(f"{aggri} {metric} for {room} is {hard_value}")
            from rasa_sdk.events import SlotSet
            return [SlotSet("aggregation" , None)]
        return []

    # "this is action reply"
    # {metric} for {room} is {hard_value}
