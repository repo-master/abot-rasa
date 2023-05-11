
from enum import Enum

from typing import Dict


class AggregationMethod(str, Enum):
    RECENT = 'recent'
    AVERAGE = 'average'
    MINIMUM = 'minimum'
    MAXIMUM = 'maximum'
    STD_DEV = 'std_dev'

AggregationOut = Dict[AggregationMethod, float]
