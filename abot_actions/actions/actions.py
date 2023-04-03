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
from typing import Any, Text, Dict, List, Tuple, TypedDict, Optional


class AggregationMethod(Enum):
  CURRENT = "current"
  AVERAGE = 'average'
  MINIMUM = 'minimum'
  MAXIMUM = 'maximum'

class AggregationResult(TypedDict):
  sensor_name : str
  result_value : str
  aggregation_method : str

class SensorMetadata(TypedDict):
  sensor_id : Optional[str]
  sensor_type : str
  sensor_unit : str


def set_sensor_units_from_type(metadata : SensorMetadata):
  if metadata.get('sensor_type') is None:
    # TODO: Warning of some sorts
    pass
  SENSORTYPE_UNIT_MAP = {
    'temp': '\u2103', # degree C symbol
    'rh': '%'
  }
  # Assign the unit if possible, else it is set to ''
  metadata['sensor_unit'] = SENSORTYPE_UNIT_MAP.get(metadata['sensor_type'], '')


def user_to_sensor_type(name):
  name = name.lower() if name else ''
  if name == 'temp' or name == 'temperature':
    return 'temp'
  elif name == 'humidity' or name == 'rh':
    return 'rh'
  elif name == 'em' or name == 'energy' or name == 'power':
    return 'em'

class ActionMetricAggregate(Action):
  def name(self):
    return "action_metric_aggregate"

  def fetch_data(self,
                 requested_sensor_id : Optional[str] = None,
                 requested_sensor_type : Optional[str] = None) -> Tuple[pd.DataFrame, SensorMetadata]:
    # TODO: Use SQLAlchemy model (already present!)
    data = pd.read_csv("sensor_data_dummy.csv")
    data['TIMESTAMP'] = pd.to_datetime(data['TIMESTAMP'])
    data.sort_values('TIMESTAMP', ascending=False, inplace=True)

    # Filter the sensor required (only one for now)
    if requested_sensor_id is not None:
      data = data.where(data['HISTORY_ID'].str.split('/')[-1] == requested_sensor_id)
    elif requested_sensor_type is not None:
      data = data.where(data['sensor_type'] == requested_sensor_type)
    else:
      #Nothing is known, raise error
      pass

    data.dropna(inplace=True)

    if len(data) > 0:
      first_row = data.iloc[0]

      # TODO: This will also be gathered from a query
      metadata : SensorMetadata = {
        'sensor_id': first_row['HISTORY_ID'],
        'sensor_type': first_row['sensor_type'],
        'sensor_unit': ''
      }
      set_sensor_units_from_type(metadata)
    else:
      metadata : SensorMetadata = {
        'sensor_id': None,
        'sensor_type': requested_sensor_type,
        'sensor_unit': ''
      }

    return data, metadata

  def perform_aggregation_on_data(self, data : pd.DataFrame, agg_method : AggregationMethod, metadata : SensorMetadata) -> Optional[AggregationResult]:
    result : float

    if len(data) == 0:
      return

    if agg_method == AggregationMethod.CURRENT:
      result = data['VALUE'].iloc[0]
    if agg_method == AggregationMethod.AVERAGE:
      result = data['VALUE'].mean()
    if agg_method == AggregationMethod.MAXIMUM:
      result = data['VALUE'].max()
    if agg_method == AggregationMethod.MINIMUM:
      result = data['VALUE'].min()

    return {
      'sensor_name': metadata['sensor_id'],
      'result_value': "%.2f%s" % (result, metadata['sensor_unit']),
      'aggregation_method': agg_method.value
    }

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
    user_req_metric = tracker.get_slot("metric")
    user_req_location = tracker.get_slot("location")
    user_req_agg_method : str = tracker.get_slot("aggregation")

    print("Got slots: Metric: %s, Location: %s, Aggregation: %s" % (
      user_req_metric, user_req_location, user_req_agg_method), flush=True)

    # TODO: More assumption magic needed

    # Either one can be set
    requested_sensor_id = None
    requested_sensor_type = user_to_sensor_type(user_req_metric)

    # Default aggregation if none of the below cases match
    aggregation = AggregationMethod.CURRENT

    # Check aggregation method provided by the user
    if user_req_agg_method is not None:
      m = user_req_agg_method.lower()
      if m == "min":
        aggregation = AggregationMethod.MINIMUM
      elif m == "max":
        aggregation = AggregationMethod.MAXIMUM
      elif m == "average":
        aggregation = AggregationMethod.AVERAGE


    # Load data
    data, metadata = self.fetch_data(requested_sensor_id, requested_sensor_type)

    # Run aggregation
    aggregated_result = self.perform_aggregation_on_data(data, aggregation, metadata)

    if aggregated_result:
      # Generate response sentence
      fmt_options = {**aggregated_result}

      response_text = "The {aggregation_method} value of {sensor_name} is {result_value}".format(**fmt_options)

      # Say the sentence
      dispatcher.utter_message(response_text)
    else:
      dispatcher.utter_message("Sorry, data for {sensor_type} isn't available yet.".format(
        sensor_type=metadata['sensor_type']
      ))

    return []
