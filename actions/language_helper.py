
from .api.statapi.schemas import AggregationOut, AggregationMethod

from typing import Optional, Union, List


def user_to_aggregation_type(name: Optional[str]) -> Union[AggregationMethod, List[AggregationMethod]]:
    #TODO: Implement multiple aggregations (and "all")
    aggregation = AggregationMethod.RECENT
    if name is not None:
        m = name.lower()
        if m == "minimum":
            aggregation = AggregationMethod.MINIMUM
        elif m == "maximum":
            aggregation = AggregationMethod.MAXIMUM
        elif m == "average":
            aggregation = AggregationMethod.AVERAGE
    return aggregation


def summary_AggregationOut(agg: AggregationOut, **kwargs) -> str:
    pass

