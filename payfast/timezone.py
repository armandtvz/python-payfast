from datetime import datetime, timedelta, timezone

import pytz

joburg = pytz.timezone('Africa/Johannesburg')




def now():
    now_utc = datetime.now(tz=timezone.utc)
    # PayFast assumes this timezone.
    now_joburg = now_utc.astimezone(joburg)
    return now_joburg




def one_week_ago():
    return now() - timedelta(days=7)




def normalize(value):
    # TODO REVIEW
    try:
        value = joburg.localize(value)
    except ValueError:
        # ValueError: Not naive datetime (tzinfo is already set)
        pass
    return value
