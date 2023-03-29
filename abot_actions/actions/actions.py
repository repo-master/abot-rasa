# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from random import randint
import pandas as pd

from rasa_sdk.types import DomainDict
from typing import Any, Text, Dict, List, Union


class ActionCheckTemprature(Action):
  def name(self):
    return "action_check_temprature"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
    return []


class ActionTest(Action):
  def name(self):
    return "action_reply_query"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
    metric = tracker.get_slot("metric")
    room = tracker.get_slot("room")
    agg_method = tracker.get_slot("aggregation")

    metric_unit = ''
    if 'temp' in metric:
      metric_unit = '\u2103' # degree C symbol
    elif 'rh' in metric:
      metric_unit = '%'

    data = pd.read_csv("temperature_data_dummy_modified.csv")

    if agg_method is None:
      latest_value = "%.2f%s" % (data["VALUE"].iloc[-1], metric_unit)
      dispatcher.utter_message("Current value of the sensor {sensor_name} is {sensor_value}".format(
        sensor_name="/TWC/VER_W1_B1_GF_B_1_temp",
        sensor_value=latest_value
      ))
    else:
      calculated_value = "%.2f%s" % (data["VALUE"].mean(), metric_unit)
      dispatcher.utter_message("Average value of the sensor {sensor_name} is {sensor_value}".format(
        sensor_name="/TWC/VER_W1_B1_GF_B_1_temp",
        sensor_value=calculated_value
      ))

    return []

  # "this is action reply"
  # {metric} for {room} is {hard_value}
