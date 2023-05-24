
from enum import Enum

from typing import Dict, Union


class AggregationMethod(str, Enum):
    RECENT = 'recent'
    AVERAGE = 'average'
    MINIMUM = 'minimum'
    MAXIMUM = 'maximum'
    STDDEV = 'stddev'
    MEDIAN = 'median'
    COUNT = 'count'
    COMPLIANCE = 'compliance'
    QUANTILE = 'quantile'
    SUMMARY = 'summary'


AggregationOut = Dict[AggregationMethod, Union[float, int]]
