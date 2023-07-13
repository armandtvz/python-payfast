try:
    from django.contrib.auth import get_user_model
except ImportError:
    get_user_model = None

import json
from typing import Union
from decimal import Decimal
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from payfast import (
    constants,
    timezone,
)
from payfast.conf import settings
from payfast.utils import get_freq_delta, get_delta_freq, get_freq_name
from payfast.signature import make_signature
from payfast.templates import render_to_string
from payfast.exceptions import (
    PayFastException,
    PayFastMinAmountException,
)
from payfast.validation import (
    PaymentValidator,
    SubscriptionPaymentValidator,
)
from payfast.serialization import PayFastJSONEncoder




class PaymentMixin:

    validator = None
    allowed_fields = {
        'merchant_id',
        'merchant_key',
        'return_url',
        'cancel_url',
        'notify_url',
        'notify_method',
        'name_first',
        'name_last',
        'email_address',
        'cell_number',
        'm_payment_id',
        'amount',
        'item_name',
        'item_description',
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
        'currency',
        'payment_method',
        'subscription_type',
        'passphrase',
        'billing_date',
        'recurring_amount',
        'frequency',
        'cycles',
        'subscription_notify_email',
        'subscription_notify_webhook',
        'subscription_notify_buyer',
        'signature',
    }
    custom_str1_fields = {
        'user_id',
        'plan_id',
        'trial',
        'run_date',
        'recurring_amount',
        'is_tokenized',
    }


    def __init__(
        self,
        amount: Union[Decimal, int],
        item_name,
        **kwargs,
    ):
        """
        ``custom_str1`` is reserved for optional JSON metadata including:
        - subscription_token
        - user_id
        - account_id
        - plan_id
        - is_upgrade

        For example::

            {
                "subscription_token": "b71be2b9-c5c4-4e1f-a44b-94d846fe75f0",
                "user_id": "456",
                "account_id": "123",
                "plan_id": "123",
                "is_upgrade": false,
                "upgrade_to_id": null
            }
        """
        from payfast import callbacks

        # Transaction details
        self.amount = Decimal(amount)
        self.amount = self.amount.quantize(Decimal('1.00'))
        self.item_name = item_name
        self.m_payment_id = kwargs.get('m_payment_id', None)
        if self.m_payment_id:
            self.m_payment_id = str(self.m_payment_id)
        self.item_description = kwargs.get('item_description', None)

        # Merchant details
        self.merchant_id = kwargs.get('merchant_id', settings.MERCHANT_ID)
        self.merchant_key = kwargs.get('merchant_key', settings.MERCHANT_KEY)
        self.return_url = kwargs.get('return_url', settings.RETURN_URL)
        self.cancel_url = kwargs.get('cancel_url', settings.CANCEL_URL)
        self.notify_url = kwargs.get('notify_url', settings.NOTIFY_URL)

        # Handle blank strings
        if not self.return_url:
            self.return_url = None
        if not self.cancel_url:
            self.cancel_url = None
        if not self.notify_url:
            self.notify_url = None

        # Customer details
        self.name_first = kwargs.get('name_first', None)
        self.name_last = kwargs.get('name_last', None)
        self.email_address = kwargs.get('email_address', None)
        self.cell_number = kwargs.get('cell_number', None)

        self.custom_int1 = kwargs.get('custom_int1', None)
        self.custom_int2 = kwargs.get('custom_int2', None)
        self.custom_int3 = kwargs.get('custom_int3', None)
        self.custom_int4 = kwargs.get('custom_int4', None)
        self.custom_int5 = kwargs.get('custom_int5', None)

        # TODO: perhaps warn if custom_str1 in kwargs
        self.subscription_token = kwargs.get('subscription_token', None)
        self.user_id = kwargs.get('user_id', None)
        self.account_id = kwargs.get('account_id', None)
        self.plan_id = kwargs.get('plan_id', None)
        self.is_upgrade = kwargs.get('is_upgrade', False)
        self.upgrade_to_id = None
        if self.is_upgrade:
            # Don't raise an exception if this is not set; it may not
            # be a requirement.
            self.upgrade_to_id = kwargs.get('upgrade_to_id', None)

        # self.custom_str1 = kwargs.get('custom_str1', None) # Reserved for general
        # self.custom_str2 = kwargs.get('custom_str2', None) # Reserved for upgrade
        self.custom_str3 = kwargs.get('custom_str3', None)
        self.custom_str4 = kwargs.get('custom_str4', None)
        self.custom_str5 = kwargs.get('custom_str5', None)

        # Transaction options
        self.email_confirmation = kwargs.get('email_confirmation', None)
        self.confirmation_address = kwargs.get('confirmation_address', None)

        # Payment methods
        self.payment_method = kwargs.get('payment_method', constants.PaymentMethod.CREDIT_CARD.value)

        responses = callbacks._payment_start(self)
        if len(responses) > 1:
            raise PayFastException(
                'You should not hook up more than one signal receiver to '
                '"payment_start".'
            )
        if not self.m_payment_id:
            try:
                self.m_payment_id = responses[0][1]
                if self.m_payment_id:
                    self.m_payment_id = str(self.m_payment_id)
            except IndexError:
                pass

        if (
            int(self.amount) < int(constants.PAYFAST_MIN_AMOUNT)
            and int(self.amount) != 0
        ):
            raise PayFastMinAmountException(self.amount)

        # PayFast does not allow payments smaller than 5.00 Rand (ZAR).
        recurring_amount = getattr(self, 'recurring_amount', None)
        if recurring_amount:
            if (
                int(recurring_amount) < 5
                and int(recurring_amount) != 0
            ):
                raise ValueError(
                    'The "recurring_amount" value provided for "Payment" '
                    'cannot be smaller than "5.00".'
                )

        try:
            self.get_django_user()
        except:
            pass

        # Ready for PayFast
        self.data_for_payfast = self.prep()
        self.validate(self.data_for_payfast)


    def get_django_user(self):
        User = None
        if get_user_model:
            User = get_user_model()

        user = None
        if User and self.user_id:
            # TODO REVIEW
            # Django is being used. Try to get the user.
            try:
                user = User.objects.get(pk=self.user_id)
            except User.DoesNotExist:
                pass

        self.user = user
        if self.user:
            if not self.name_first:
                self.name_first = self.user.first_name
            if not self.name_last:
                self.name_last = self.user.last_name
            if not self.email_address:
                self.email_address = self.user.email


    @property
    def custom_str1(self):
        trial_started_at = getattr(self, 'trial_started_at', None)
        trial_expires_at = getattr(self, 'trial_expires_at', None)
        trial = [trial_started_at, trial_expires_at]
        value = json.dumps({
            'user_id': self.user_id,
            'plan_id': self.plan_id,

            'trial': trial,
            'run_date': getattr(self, 'billing_date', None),
            'recurring_amount': getattr(self, 'recurring_amount', None),
            'is_tokenized': getattr(self, 'is_tokenized', False),
        }, cls=PayFastJSONEncoder)
        length = len(value)
        if length > 255:
            raise ValueError(
                f'"custom_str1" exceeds PayFast character limit of 255. '
                f'Length: {length}. '
                f'custom_str1: {value}. '
            )
        return value


    @property
    def metadata(self):
        return self.custom_str1


    def prep(self):
        data = {}
        # Don't get private attributes or magic methods; those are not
        # meant to be sent to PayFast.
        attributes = [a for a in dir(self) if not a.startswith('_')]
        for attr in attributes:
            if attr not in self.allowed_fields:
                continue

            value = getattr(self, attr)
            if callable(value):
                continue

            if isinstance(value, Decimal):
                value = str(value)

            if attr in ['email_confirmation']:
                if value is True:
                    value = constants.BooleanInteger.ON.value
                elif value is False:
                    value = constants.BooleanInteger.OFF.value
                else:
                    value = None

            if attr in ['billing_date']:
                if isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d')

            if isinstance(value, bool):
                if value:
                    value = 'true'
                else:
                    value = 'false'

            data[attr] = value
        signature = make_signature(data, a12y=False)
        data['signature'] = signature
        return data


    def validate(self, data):
        self.validator(**data)


    def get_inputs(self, data: dict):
        inputs = []
        for key, value in data.items():
            if key == 'passphrase':
                continue
            if key not in self.allowed_fields:
                raise ValueError(
                    f'Form field requested for PayFast form, "{key}", is not '
                    f'a valid PayFast field.'
                )
            if value is None:
                continue
            inputs.append({
                'type': 'hidden',
                'name': key,
                'value': value,
            })
        return inputs


    def get_form(self):
        data = self.data_for_payfast
        inputs = self.get_inputs(data)
        context = {
            **data,
            'inputs': inputs,
            'debug': settings.DEBUG,
            'payfast_process_url': settings.PROCESS_URL,
            'button_name': 'Proceed to PayFast',
        }
        rendered = render_to_string('payfast/form.html', context)
        return rendered




class Payment(PaymentMixin):

    validator = PaymentValidator




class FreeTrialMixin:

    def __init__(self, *args, **kwargs):
        # Handle free trials
        self.trial_started_at = None
        self.trial_expires_at = None

        self.free_days = kwargs.get('free_days', None)
        if self.free_days and 'billing_date' in kwargs:
            raise ValueError(
                'You cannot set "free_days" and "billing_date" '
                'for a "SubscriptionPayment".'
            )

        self.free_delta = kwargs.get('free_delta', None)
        if self.free_delta and 'billing_date' in kwargs:
            raise ValueError(
                'You cannot set "free_delta" and "billing_date" '
                'for a "SubscriptionPayment".'
            )

        if self.free_days and self.free_delta:
            raise ValueError(
                'You cannot set both "free_delta" and "free_days" '
                'for a "SubscriptionPayment".'
            )

        if self.free_delta:
            if not (
                isinstance(self.free_delta, timedelta)
                or isinstance(self.free_delta, relativedelta)
            ):
                raise ValueError(
                    '"free_delta" must be an instance of either "timedelta" '
                    'or "relativedelta" for a "SubscriptionPayment".'
                )

        if self.free_days is not None:
            try:
                self.free_days = int(self.free_days)
                if self.free_days < 0:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError(
                    '"free_days" must be an integer greater than or equal to 0.'
                )
            if self.free_days > 0:
                if not self.recurring_amount:
                    raise ValueError(
                        'You are starting a "SubscriptionPayment" '
                        'with a positive value for "free_days" but you '
                        'did not set "recurring_amount".'
                    )
                amount = Decimal(0.00)
                amount = amount.quantize(Decimal('1.00'))
                self.free_delta = relativedelta(days=self.free_days)

        if self.free_delta:
            self.billing_date = timezone.now() + self.free_delta
            # We don't bill on the day of the trial ending; we bill the day after
            self.billing_date += relativedelta(days=1)
            self.trial_started_at = timezone.now()
            self.trial_expires_at = self.billing_date
        super().__init__(*args, **kwargs)




class SubscriptionPayment(FreeTrialMixin, Payment):

    validator = SubscriptionPaymentValidator


    def __init__(self, amount, item_name, **kwargs):
        frequency = kwargs.get('frequency', constants.Frequency.MONTHLY.value)
        if isinstance(frequency, relativedelta):
            frequency = get_delta_freq(frequency)
        self.frequency = frequency
        self.cycles = kwargs.get('cycles', constants.Cycles.INDEFINITE.value)
        try:
            int(self.cycles)
        except:
            raise
        self.subscription_type = constants.SubscriptionType.REGULAR.value
        self.is_tokenized = False

        self.billing_date = kwargs.get('billing_date', timezone.now())
        self.recurring_amount = kwargs.get('recurring_amount', None)
        if not amount and not self.recurring_amount:
            raise ValueError(
                'You must provide a value for "recurring_amount" argument '
                'if no value is provided for "amount".'
            )
        if self.recurring_amount:
            self.recurring_amount = Decimal(self.recurring_amount)
            self.recurring_amount = self.recurring_amount.quantize(Decimal('1.00'))
        else:
            amount = Decimal(amount)
            amount = amount.quantize(Decimal('1.00'))
            self.recurring_amount = amount
        super().__init__(amount, item_name, **kwargs)


    @property
    def freq_delta(self):
        return get_freq_delta(self.frequency)




class TokenizedPayment(Payment):

    def __init__(self, amount, item_name, **kwargs):
        self.subscription_type = constants.SubscriptionType.TOKENIZATION.value
        self.is_tokenized = True
        super().__init__(amount, item_name, **kwargs)




# TODO REVIEW
class TokenizedSub(SubscriptionPayment):

    def __init__(self, amount, item_name, **kwargs):
        super().__init__(amount, item_name, **kwargs)
        self.subscription_type = constants.SubscriptionType.TOKENIZATION.value
        self.is_tokenized = True
        del self.frequency
        del self.cycles
        del self.recurring_amount
        # Prep again
        self.data_for_payfast = self.prep()




class OnsitePayment(Payment):

    def __init__(self, amount, item_name, **kwargs):
        # Required unless mobile registration
        self.email_address = kwargs.get('email_address', None)

        # Required if email is not set
        self.cell_number = kwargs.get('cell_number', None)
        super().__init__(amount, item_name, **kwargs)
