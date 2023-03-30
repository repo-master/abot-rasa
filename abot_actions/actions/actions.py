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
from enum import Enum, auto
from typing import Any, Text, Dict, List, Union


class AggregationMethod(Enum):
  CURRENT = auto()
  AVERAGE = auto()
  MINIMUM = auto()
  MAXIMUM = auto()

class ActionMetricAggregate(Action):
  def name(self):
    return "action_metric_aggregate"

  def run_aggregation_on_data(self, data : pd.DataFrame, agg_method : AggregationMethod, unit : str = '') -> str:
    result : float

    if agg_method == AggregationMethod.CURRENT:
      result = data['VALUE'].iloc[-1]
    if agg_method == AggregationMethod.AVERAGE:
      result = data['VALUE'].mean()
    if agg_method == AggregationMethod.MAXIMUM:
      result = data['VALUE'].max()
    if agg_method == AggregationMethod.MINIMUM:
      result = data['VALUE'].min()
    return "%.2f%s" % (result, unit)

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
    metric = tracker.get_slot("metric")
    location = tracker.get_slot("location")
    agg_method : str = tracker.get_slot("aggregation")

    print("Got slots:", metric, location, agg_method, flush=True)

    metric_unit = ''
    if 'temp' in metric:
      metric_unit = '\u2103' # degree C symbol
    elif 'rh' in metric:
      metric_unit = '%'

    data = pd.read_csv("temperature_data_dummy_modified.csv")
    aggregation = AggregationMethod.CURRENT

    if agg_method is not None:
      m = agg_method.lower()
      if m == "min":
        aggregation = AggregationMethod.MINIMUM
      elif m == "max":
        aggregation = AggregationMethod.MAXIMUM
      elif m == "average":
        aggregation = AggregationMethod.AVERAGE

    aggregated_result = self.run_aggregation_on_data(data, aggregation, metric_unit)

    fmt_options = {}

    if aggregation == AggregationMethod.CURRENT:
      fmt_options['agg'] = "current"
    if aggregation == AggregationMethod.AVERAGE:
      fmt_options['agg'] = "average"
    if aggregation == AggregationMethod.MINIMUM:
      fmt_options['agg'] = "minimum"
    if aggregation == AggregationMethod.MAXIMUM:
      fmt_options['agg'] = "maximum"

    fmt_options['sensor_name'] = "VER_W1_B1_GF_B_1_temp"
    fmt_options['sensor_value'] = aggregated_result

    response_text = "The {agg} value of {sensor_name} is {sensor_value}".format(**fmt_options)

    dispatcher.utter_message(response_text)

    return []

  # "this is action reply"
  # {metric} for {location} is {hard_value}
