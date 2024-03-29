
from typing import Dict, List

import pandas as pd


def describe_all_data_insights(insights: list) -> List[Dict[str, str]]:
    # TODO: Insights to string automatic using Transformers model

    messages: List[Dict[str, str]] = []

    # Count
    insight_type_counts: Dict[str, int] = {}
    for detected_insight in insights:
        if detected_insight['type'] not in insight_type_counts.keys():
            insight_type_counts[detected_insight['type']] = 0
        insight_type_counts[detected_insight['type']] += 1

    if len(insight_type_counts) > 0:
        counts = '\n'.join([
            "- %d %s(s)" % (v, k) for k, v in insight_type_counts.items()
        ])
        messages.append(dict(text="In the selected data, I've found:\n%s" % counts))

    for i, detected_insight in enumerate(insights):
        i_type = detected_insight['type']
        if i_type == 'outlier':
            dp: dict = detected_insight['data_point']

            outlier_value = dp['value']
            occurrence_time = pd.Timestamp.fromisoformat(dp.get('timestamp', ''))
            occurrence_time_formatted = occurrence_time.strftime("%Y/%m/%d at %H:%M:%S %p")
            display_unit = dp.get('display_unit', '')

            if dp['is_extreme_high']:
                dp_type = "high value"
            elif dp['is_extreme_low']:
                dp_type = "low value"
            else:
                dp_type = "value"

            outlier_format = "{timestamp}: {value:.2f}{unit}\nExtreme *{high_or_low}*"
            messages.append(dict(text=outlier_format.format(
                timestamp=occurrence_time_formatted,
                value=outlier_value,
                unit=display_unit,
                high_or_low=dp_type
            )))
        # HACK: Exhaust list for now
        if i > 2 and i < len(insights):
            messages.append(dict(text="More outliers present, but can't display all of them."))
            break
    else:
        if len(insights) > 0:
            messages.append(dict(text="There aren't any other significant issues present in the data."))
        if insight_type_counts.get('outlier', 0) == 0:
            messages.append(
                dict(text="There are no outliers present in the data, all values are within normal range."))

    return messages
