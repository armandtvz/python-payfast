import hashlib
import urllib.parse
from urllib.parse import quote_plus
from urllib.parse import urlencode
from urllib.parse import urljoin as join
from collections import OrderedDict

from payfast.conf import settings




def make_querystring(payfast_data, salt=settings.SALT_PASSPHRASE, a12y=False):
    """
    List in format:

        list_for_get_string = [
            ('merchant_id', data['merchant_id']),
            ('merchant_key', data['merchant_key']),
            ('amount', data['amount']),
            ('item_name', data['item_name']),
            ('passphrase', data['passphrase'])
        ]
    """
    correct_order = [
        'merchant_id',
        'merchant_key',
        'return_url',
        'cancel_url',
        'notify_url',

        'name_first',
        'name_last',
        'email_address',
        'cell_number',

        'm_payment_id',

        # From the ITN
        'pf_payment_id',
        'payment_status',

        'amount',
        'item_name',
        'item_description',

        # From the ITN
        'amount_gross',
        'amount_fee',
        'amount_net',

        'custom_int1',
        'custom_int2',
        'custom_int3',
        'custom_int4',
        'custom_int5',
        'custom_str1',
        'custom_str2',
        'custom_str3',
        'custom_str4',
        'custom_str5',

        'email_confirmation',
        'confirmation_address',

        'payment_method',

        'subscription_type',
        'token',
        'billing_date',
        'recurring_amount',
        'frequency',
        'cycles',
        'subscription_notify_email',
        'subscription_notify_webhook',
        'subscription_notify_buyer',

        # From ITN
        'signature',
    ]
    data = payfast_data
    list_for_get_string = []
    keys = list(payfast_data.keys())
    sorted_keys = []

    if a12y:
        keys.append('passphrase')
        sorted_keys = sorted(keys)
    else:
        sorted_keys = sorted(keys, key=correct_order.index)

    for key in sorted_keys:
        if key == 'signature':
            continue
        if key == 'passphrase':
            value = salt
        else:
            value = payfast_data[key]

        if value is not None:
            value = str(value)
            list_for_get_string.append(
                (key, value),
            )

    if not a12y:
        list_for_get_string.append(
            ('passphrase', salt),
        )
    ordered_dict = OrderedDict(list_for_get_string)
    get_string = urlencode(ordered_dict)
    return get_string




def make_signature(payfast_data, a12y=False):
    querystring = make_querystring(payfast_data, a12y=a12y)
    signature = hashlib.md5(querystring.encode()).hexdigest()
    signature = signature.lower()
    return signature
