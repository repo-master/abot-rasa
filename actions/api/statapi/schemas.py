
from enum import Enum

from typing import Dict


class AggregationMethod(str, Enum):
    RECENT = 'recent'
    AVERAGE = 'average'
    MINIMUM = 'minimum'
    MAXIMUM = 'maximum'

AggregationOut = Dict[AggregationMethod, float]
