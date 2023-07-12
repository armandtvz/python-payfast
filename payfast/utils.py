import os
import csv
import copy
from io import StringIO
from decimal import Decimal
from urllib.parse import urljoin as join

from dateutil.relativedelta import relativedelta

from payfast import timezone, constants
from payfast.conf import settings




def urljoin(parts):
    url = ''
    for part in parts:
        # urljoin automatically takes care of extra/missing '/'
        url = join(url + '/', part)
    return url




def get_ip(request):
    addr = None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        addr = x_forwarded_for.split(',')[0]
    else:
        addr = request.META.get('REMOTE_ADDR')
    return addr




def prorate(amount, start, end, usage=False) -> Decimal:
    """
    (days_left / total_days) * amount
    (days_used / total_days) * amount
    """
    now = timezone.now().date()
    start = start.date()
    end = end.date()
    if not isinstance(amount, Decimal):
        amount = Decimal(amount)

    days_left = (end - now).days
    days_used = (now - start).days
    total_days = (end - start).days
    if total_days < 0:
        raise ValueError('"total_days" cannot be negative.')
    if total_days == 0:
        diff = Decimal(0)
        return diff.quantize(Decimal('1.00'))

    prorata_share = Decimal(days_left) / Decimal(total_days)
    if usage:
        prorata_share = Decimal(days_used) / Decimal(total_days)
    diff = Decimal(prorata_share) * Decimal(amount)
    return diff.quantize(Decimal('1.00'))




def csv_to_dict(csv_string):
    buffer = StringIO(csv_string)
    reader = csv.DictReader(buffer)
    data_dict = [row for row in reader]
    return data_dict




def get_freq_delta(freq):
    kwargs = {}
    freq = int(freq)
    if freq == constants.Frequency.DAILY.value:
        kwargs = {'days': 1}

    elif freq == constants.Frequency.WEEKLY.value:
        kwargs = {'weeks': 1}

    elif freq == constants.Frequency.MONTHLY.value:
        kwargs = {'months': 1}

    elif freq == constants.Frequency.QUARTERLY.value:
        kwargs = {'months': 3}

    elif freq == constants.Frequency.BIANNUALLY.value:
        kwargs = {'months': 6}

    elif freq == constants.Frequency.ANNUAL.value:
        kwargs = {'years': 1}
    delta = relativedelta(**kwargs)
    return delta




def get_delta_freq(delta):
    freq = None
    if not isinstance(delta, relativedelta):
        delta_type = str(type(delta))
        raise TypeError(
            f'"delta" argument in "get_delta_freq" must be "relativedelta" '
            f'and not {delta_type}.'
        )
    if delta == relativedelta(days=1):
        freq = constants.Frequency.DAILY.value

    elif delta == relativedelta(weeks=1):
        freq = constants.Frequency.WEEKLY.value

    elif delta == relativedelta(months=1):
        freq = constants.Frequency.MONTHLY.value

    elif delta == relativedelta(months=3):
        freq = constants.Frequency.QUARTERLY.value

    elif delta == relativedelta(months=6):
        freq = constants.Frequency.BIANNUALLY.value

    elif delta == relativedelta(years=1):
        freq = constants.Frequency.ANNUAL.value
    return freq




def get_freq_name(freq: int):
    freq = int(freq)
    value = freq
    if value == 1:
        return 'daily'

    elif value == 2:
        return 'weekly'

    elif value == 3:
        return 'monthly'

    elif value == 4:
        return 'quarterly'

    elif value == 5:
        return 'biannually'

    elif value == 6:
        return 'yearly'
    raise ValueError(f'No such frequency with integer "{freq}".')




def make_key(token):
    namespace = settings.CACHE_KEY_PREFIX
    token = str(token)
    token = token.replace('-', '')
    key = f'{namespace}:subscription:{token}'
    return key




def cache_bust(token):
    from payfast import PayFast
    payfast = PayFast()

    try:
        from django.core.cache import cache
        from django.apps import apps
    except ImportError:
        return

    if not apps.ready:
        return

    key = make_key(token)
    cache.delete(key)

    payfast.subs.get(token, cache=True)
