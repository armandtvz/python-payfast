import json
from datetime import datetime
from decimal import Decimal

from payfast import timezone




datetime_fields = [
    'run_date',
    'billing_date',

    'trial_started_at',
    'trial_expires_at',
]
decimal_fields = [
    'amount',
    'amount_gross',
    'amount_fee',
    'amount_net',
    'recurring_amount',
]
integer_fields = [
    'merchant_id',

    'amount_cents',

    'custom_int1',
    'custom_int2',
    'custom_int3',
    'custom_int4',
    'custom_int5',

    'subscription_type',
    'frequency',
    'cycles',
    'cycles_complete',
    'status',
]
str_fields = [
    'merchant_key',
    'return_url',
    'cancel_url',
    'notify_url',

    'name_first',
    'name_last',
    'email_address',
    'cell_number',

    'm_payment_id',

    # According to ITN docs this is a string as received from PayFast
    # even though it looks like an integer. However, we can't make any
    # assumptions about the type.
    'pf_payment_id',
    'payment_status',

    'item_name',
    'item_description',

    'custom_str1',
    'custom_str2',
    'custom_str3',
    'custom_str4',
    'custom_str5',

    'confirmation_address',
    'payment_method',

    'token',
    'sub_token',
    'subscription_token',
    'signature',

    'status_reason',
    'status_text',
]
boolean_fields = [
    'email_confirmation',
    # 'subscription_notify_email',
    # 'subscription_notify_webhook',
    # 'subscription_notify_buyer',

    'is_tokenized_card',
]




class PayFastJSONEncoder(json.JSONEncoder):


    def handle_fields(self, obj):
        enc = {}
        for field in datetime_fields:
            value = getattr(obj, field, None)
            if not value:
                continue
            value = value.isoformat()
            enc[field] = value

        for field in decimal_fields:
            value = getattr(obj, field, None)
            if not value:
                continue
            value = str(value)
            enc[field] = value

        for field in integer_fields:
            value = getattr(obj, field, None)
            if not value:
                continue
            value = int(value)
            enc[field] = value

        for field in str_fields:
            value = getattr(obj, field, None)
            if not value:
                continue
            value = str(value)
            enc[field] = value

        for field in boolean_fields:
            value = getattr(obj, field, None)
            if not value:
                continue
            value = bool(value)
            enc[field] = value
        return enc


    def default(self, obj):
        from payfast.api.subscriptions import Subscription

        if isinstance(obj, Decimal):
            return str(obj)

        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%dT%H:%M:%S')

        if isinstance(obj, Subscription):
            return self.handle_fields(obj)

        return super().default(obj)




def decoder(values):
    transformed = {}
    for key, value in values.items():
        if key in decimal_fields:
            value = Decimal(value)

        elif key in integer_fields:
            value = int(value)

        elif key in datetime_fields:
            value = datetime.fromisoformat(value)

        transformed[key] = value
    return transformed
