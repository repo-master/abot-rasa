
from dateutil.relativedelta import relativedelta


GRAINS = {
    'second': relativedelta(seconds=1),
    'minute': relativedelta(minutes=1),
    'hour': relativedelta(hours=1),
    'day': relativedelta(days=1),
    'week': relativedelta(weeks=1),
    'month': relativedelta(months=1),
    'quarter': relativedelta(months=3),
    'year': relativedelta(years=1)
}
