
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
        '\n'.join([
            "- %d %s(s)" % (v, k) for k, v in insight_type_counts.items()
        ])
        messages.append(dict(text="In the selected data, I've found:\n%s"))

    for detected_insight in insights:
        i_type = detected_insight['type']
        if i_type == 'outlier':
            dp: dict = detected_insight['data_point']

            outlier_value = dp['value']
            occurrence_time = pd.Timestamp.fromisoformat(dp.get('timestamp', ''))
            occurrence_time_formatted = occurrence_time.strftime("%Y/%m/%d at %H:%M:%S %p")
            display_unit = dp.get('display_unit', '')

            if dp['is_extreme_high']:
                dp_type = "much higher compared to"
            elif dp['is_extreme_low']:
                dp_type = "much lower compared to"
            else:
                dp_type = "comparable to"

            outlier_format = "There is data point on {timestamp} with the value {value:.2f}{unit}. This seems to be an extreme value which is *{high_or_low}* the rest of the points in the timerange."
            messages.append(dict(text=outlier_format.format(
                timestamp=occurrence_time_formatted,
                value=outlier_value,
                unit=display_unit,
                high_or_low=dp_type
            )))
        break
    else:
        messages.append(dict(text="Sorry, I can't provide any insights on the data."))

    return messages
