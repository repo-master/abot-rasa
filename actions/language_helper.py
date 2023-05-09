
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


def summary_AggregationOut(agg: AggregationOut, unit_symbol: str = '', **kwargs) -> str:
    def _agg_str(am: AggregationMethod, value: float) -> str:
        return '{agg_method}: {value:.2f}{unit_symbol}'.format(
            agg_method=am.value.title(),
            value=value,
            unit_symbol=unit_symbol
        )
    if len(agg.keys()) == 1:
        # Directly give that value without a list
        am, val = next(iter(agg.items()))
        return _agg_str(AggregationMethod(am), val)
    elif len(agg.keys()) > 1:
        # Prepare a markdown list-style output
        return '\n'.join(["- " + _agg_str(AggregationMethod(am), val) for am, val in agg.items()])

