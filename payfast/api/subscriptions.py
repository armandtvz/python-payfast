# TODO: add TokenizedSubscription

import json
import decimal
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Union

from dateutil.relativedelta import relativedelta

from payfast import constants, timezone
from payfast.base import Resource
from payfast.decorators import cached
from payfast.utils import (
    urljoin,
    prorate,
    cache_bust,
    get_freq_delta,
)
from payfast.conf import settings
from payfast.exceptions import PayFastAPIException, PayFastException
from payfast.serialization import PayFastJSONEncoder
from payfast.payment import (
    Payment,
    SubscriptionPayment,
    TokenizedPayment,
)

logger = logging.getLogger('payfast.api')




class Upgrade:
    # TODO:
    # Add flag to allow start_upgrade to prep for upgrade without
    # requiring any payment. Therefore, making all upgrades is_immediate=True.
    #
    # TODO:
    # Configuration for proration including minimum amount at which
    # a prorated amount is considered payable.

    def __init__(
        self,
        sub,
        amount,
        item_name,
        upgrade_to_period: list=None,
        cancel=False,
        **kwargs,
    ):
        """
        Upgrade this subscription.

        #. Create ``Payment`` with prorated amount (not a ``SubscriptionPayment``).
        #. Return initialized ``Payment`` object.
        #. The ``Payment`` must then be used to redirect the user to PayFast.
        #. Receive the successful/cancelled payment via the ITN webhook.

        The upgrade can be handled in the ``payment_done`` callback/Django signal.

        If the subscription is still a trial return ``None`` because payment
        is not required in such a case. However, that being said, the
        subscription still needs to be updated on PayFast. But considering
        that this method's only responsibility is to prepare a ``Payment``
        object for the upgrade this method leaves it to the user of this
        library to handle the ``None`` case.

        :param amount: The amount to upgrade the subscription to.
        :param item_name:
        """
        self.sub = sub
        self.token = sub.token
        self.amount = Decimal(amount)
        self.amount = self.amount.quantize(Decimal('1.00'))
        self.item_name = item_name
        self.payment = None
        self.is_immediate = False

        self.user_id = kwargs.pop('user_id', None)
        self.plan_id = kwargs.pop('plan_id', None)
        self.upgrade_to_id = kwargs.pop('upgrade_to_id', None)
        self.cancel = cancel
        if settings.PAYFAST_UPDATE_BUG:
            self.cancel = True

        self.upgrade_to = self.amount
        self.upgrade_from = self.sub.amount

        start = self.sub.start_date
        end = self.sub.run_date
        upgrade_to_start = start
        upgrade_to_end = end
        if isinstance(upgrade_to_period, list):
            if len(upgrade_to_period) == 2:
                # If the period is provided it probably means the user is
                # upgrading to a different billing frequency which we don't
                # allow to update in this library. Rather cancel and start a
                # a new subscription.
                self.cancel = True
                upgrade_to_start = upgrade_to_period[0]
                upgrade_to_end = upgrade_to_period[1]

        prorate_left = prorate(
            self.upgrade_to,
            upgrade_to_start,
            upgrade_to_end,
            usage=False,
        )
        prorate_used = prorate(self.upgrade_from, start, end, usage=True)
        self.prorated_amount = prorate_left - prorate_used
        if self.prorated_amount < 0:
            self.prorated_amount = 0

        # This package maintains that if the amounts are equal
        # it's a downgrade and can therefore not be an upgrade.
        # Similarly, if the upgrade means the customer will
        # now be billed less per billing cycle then this is
        # also not an upgrade.
        if self.upgrade_to <= self.upgrade_from:
            raise PayFastException(
                f'You are trying to perform an upgrade where you should '
                f'actually be performing a downgrade. New amount must be '
                f'larger than current/old amount. '
                f'Subscription token: "{self.sub.token}". '
                f'Upgrading from "{upgrade_from}" ZAR. '
                f'Upgrading to "{upgrade_to}" ZAR. '
            )

        self.payment_kwargs = {}
        update_fields = [
            'cycles',
            'run_date',
            'amount_cents',
            'amount',
        ]
        for key, value in kwargs.items():
            if key not in update_fields:
                self.payment_kwargs[key] = value

        self.payment_kwargs['user_id'] = self.user_id
        if self.cancel:
            self.payment_kwargs['run_date'] = self.sub.run_date
            self.payment_kwargs['recurring_amount'] = self.amount

        if not sub.is_active:
            raise PayFastException(
                f'Cannot upgrade subscription that is not active '
                f'(token "{sub.token}").'
            )
        if sub.is_trial:
            # No need to ask for payment when still in trial period.
            # This subscription can be upgraded (read: updated) immediately.
            # Use Upgrade.do() for this.
            self.is_immediate = True
        else:
            upgrade_json = self.json()
            self.payment_kwargs['custom_str2'] = upgrade_json
            self.payment = self.create_payment(**self.payment_kwargs)

        if not self.payment:
            self.is_immediate = True


    def __repr__(self):
        return (
            f'<{self.__class__.__name__} '
            f'from {self.upgrade_from} to {self.upgrade_to}>'
        )


    def create_payment(self, **kwargs) -> Payment:
        # REMOVE HACK
        now = timezone.now().date()
        run_date = self.sub.run_date.date()
        diff = (run_date - now).total_seconds()
        # 172800 seconds == 2 days
        if (run_date <= now) or (diff < 172800):
            raise PayFastException(
                f'Cannot upgrade subscription "{self.token}" because the '
                f'subscription run date ({run_date}) is too close to '
                f'now ({now}).'
            )
        if not self.cancel:
            if self.prorated_amount < constants.PAYFAST_MIN_AMOUNT:
                return

        payment = Payment(
            self.prorated_amount,
            self.item_name,
            **kwargs,
        )
        if self.cancel:
            payment = SubscriptionPayment(
                self.prorated_amount,
                self.item_name,
                billing_date=self.sub.run_date,
                **kwargs,
            )
        # m_payment_id = kwargs.get('m_payment_id', None)
        # if not m_payment_id:
        #     # If the merchant payment ID is not provided check to see if
        #     # the callback used in Payment.__init__ returned an m_payment_id.
        #     m_payment_id = payment.m_payment_id
        # if not m_payment_id:
        #     raise ValueError(
        #         '"m_payment_id" is required to start the upgrade process. '
        #         'Either pass the value via the kwargs or return the '
        #         '"m_payment_id" in the "payment_start" callback/Django signal.'
        #     )
        return payment


    def json(self):
        d = {
            'amount': self.amount,
            'token': self.token,
            'item_name': self.item_name,
            'plan_id': self.plan_id,
            'upgrade_to_id': self.upgrade_to_id,
            'cancel': self.cancel,
        }
        return json.dumps(d, cls=PayFastJSONEncoder)


    def do(self, itn=None):
        from payfast.itn import ITN

        if not self.is_immediate and not isinstance(itn, ITN):
            # REMOVE HACK
            raise PayFastException(
                'You cannot run "Upgrade.do()" on an upgrade that requires '
                'payment. Therefore, this subscription cannot be '
                'upgraded immediately.'
            )
        if self.cancel:
            # REMOVE HACK
            return self.sub.cancel()
        return self.sub.update(amount=self.amount)




class SubscriptionBase:

    def __init__(self, data):
        if not isinstance(data, dict):
            # The data argument would generally come straight from the
            # RequestsTransport response. Therefore, if the transport
            # somehow handles the response incorrectly a boolean or
            # some other type might be used instead of a dictionary.
            raise ValueError(
                '"data" argument for "Subscription" must be a dictionary.'
            )

        self.data = data
        values = {}
        for field, value in data.items():
            value = data.get(field, None)
            if field == 'amount':
                # PayFast returns the amount in cents.
                # Convert it to something more obvious.
                self.amount_cents = int(value)
                value = Decimal(value) / Decimal(100)
                value = value.quantize(Decimal('1.00'))

            if field == 'run_date':
                value = datetime.fromisoformat(value)
                value = timezone.normalize(value)

            if field in ['cycles', 'cycles_complete', 'frequency', 'status']:
                value = int(value)

            setattr(self, field, value)

        if hasattr(self, 'frequency'):
            self.freq = self.frequency


    @property
    def is_active(self):
        if self.status_text == constants.SubscriptionStatus.ACTIVE.value:
            return True
        return False


    @property
    def is_cancelled(self):
        if self.status_text == constants.SubscriptionStatus.CANCELLED.value:
            return True
        return False


    def cancel(self):
        from payfast import PayFast
        payfast = PayFast()
        return payfast.subscriptions.cancel(self.token)


    def update_card_link(self, return_url=None) -> str:
        from payfast import PayFast
        payfast = PayFast()
        return payfast.subscriptions.update_card_link(self.token, return_url)




class Subscription(SubscriptionBase):

    @property
    def start_date(self):
        if self.cycles_complete == 0:
            return self.run_date
        cycles_complete = self.freq_delta * self.cycles_complete
        start = self.run_date - cycles_complete
        return start


    @property
    def end_date(self):
        if not self.cycles:
            return
        cycles = self.freq_delta * self.cycles
        end = self.start_date + cycles
        return end


    @property
    def is_trial(self):
        """
        A subscription is in a free trial if:

        - ``cycles_complete`` is smaller than 1. This means that
          the customer has not completed a billing cycle yet and;

        - ``run_date`` is in the future.
        """
        now = timezone.now().date()
        run_date = self.run_date.date()
        if self.cycles_complete < 1:
            return True
        return False


    @property
    def freq_delta(self) -> relativedelta:
        """
        Return the frequency as a ``relativedelta``.
        """
        return get_freq_delta(self.frequency)


    def get_next_charge(self) -> datetime:
        """
        Returns the ``run_date`` which is the next date at which the customer
        will be billed.
        """
        return self.run_date


    def upgrade(
        self,
        amount,
        item_name,
        upgrade_to_period: list=None,
        **kwargs
    ) -> Upgrade:
        upgrade = Upgrade(
            sub=self,
            amount=amount,
            item_name=item_name,
            upgrade_to_period=upgrade_to_period,
            **kwargs,
        )
        return upgrade


    def downgrade(self, amount: Decimal, **kwargs):
        """
        Downgrade this subscription.

        * No payment is required for a downgrade.
        * Accepts the same arguments as ``payfast.api.Subscriptions.update``
          except for the ``token`` and ``amount_cents`` arguments.

        #. Update this subscription using the PayFast API.

        :param amount: The amount to downgrade to.
        """
        from payfast import PayFast
        payfast = PayFast()

        if settings.PAYFAST_UPDATE_BUG:
            raise PayFastException(
                'Cannot downgrade subscription until the PayFast '
                'update bug is fixed. Cancel the subscription, then '
                'have the user start a new subscription.'
            )

        try:
            kwargs.pop('token')
        except KeyError:
            pass
        if not self.is_active:
            raise PayFastException(
                f'Cannot downgrade subscription that is not active '
                f'(token "{self.token}").'
            )
        amount_cents = int(amount * 100)
        kwargs['amount_cents'] = amount_cents
        return payfast.subscriptions.update(
            self.token,
            **kwargs,
        )


    def is_unpaid(self):
        """
        According to PayFast support the subscription ``run_date``
        won't be changed after payment failures. The ``run_date``
        will only be updated after a successful payment.
        """
        now = timezone.now().date()
        run_date = self.run_date.date()
        if now < run_date:
            return False
        if self.unpaid_cutoff_date < now:
            return True
        return False


    def is_paid(self):
        return not self.is_unpaid()


    @property
    def unpaid_cutoff_date(self):
        # For this to work properly `self.is_trial` must not take
        # the `run_date` into account; only `cycles_complete`.
        # This is due to the run_date no longer being in the future
        # if there was a payment failure.
        if self.is_trial:
            cutoff = self.run_date + timedelta(days=1)
            return cutoff
        cutoff = self.run_date + timedelta(days=settings.GRACE_PERIOD_DAYS)
        cutoff = cutoff.date()
        return cutoff


    def payment_missed(self) -> bool:
        if self.is_unpaid():
            return True
        now = timezone.now().date()
        run_date = self.run_date.date()
        if run_date < now:
            return True
        return False


    def change_billing_day(self, day: int) -> bool:
        from payfast import PayFast
        payfast = PayFast()

        # TODO: take billing cycle into account
        # TODO: prorate?

        if self.is_trial:
            raise PayFastException(
                'You cannot change the billing day for a subscription still in '
                'a free trial. Doing so may shorten or extend the trial.'
            )

        now = timezone.now().date()
        run_date = self.run_date.date()
        if not isinstance(day, int):
            raise ValueError(
                '"day" argument for "change_billing_day" must be an integer.'
            )

        if not (0 < day <= 28):
            raise ValueError(
                '"day" argument for "change_billing_day" must be an integer '
                'between 1 and 28 (0 < day <= 28).'
            )

        if day == run_date.day:
            # Nothing to do.
            return True

        if run_date < now:
            # This is not supposed to happen.
            # This could be that there were payment failures.
            raise PayFastException(
                'Cannot change billing day because "run_date" is in the past '
                'which means that this subscription may have had one or more '
                'payment failures.'
            )

        diff = (run_date - now).total_seconds()
        diff = abs(int(diff))
        # 172800 seconds == 2 days
        if diff >= 172800:
            # If the diff is negative it means the run_date is in the past
            # which is unlikely to be the case
            raise PayFastException(
                'Cannot change billing day this close to "run_date".'
            )
        if now == run_date or diff == 0:
            # Cannot change the billing day right now because the
            # payment is due for today on PayFast. Changing it now
            # might cause problems.
            raise PayFastException(
                'Cannot change billing day on day that payment is due.'
            )

        new_run_date = run_date.replace(day=day)
        payfast.subscriptions.update(self.token, run_date=new_run_date)
        return True


    def update(self, **kwargs):
        from payfast import PayFast
        payfast = PayFast()
        return payfast.subscriptions.update(self.token, **kwargs)




class Card(SubscriptionBase):
    pass




class SubscriptionBaseResource:

    key = 'subscriptions'


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_card = False


    def fetch(self, *args, **kwargs):
        """
        Just an alias for ``get`` because this is what the endpoint is
        called on PayFast's API.
        """
        return self.get(*args, **kwargs)


    @cached
    def get(self, token, **kwargs):
        """
        GET ``/subscriptions/:token/fetch``

        Example response of a subscription managed by PayFast
        (not adhoc tokenization):

        .. code-block::

            {
                "code": 200,
                "status": "success",
                "data": {
                    "response": {
                        "amount": 1628,
                        "cycles": 14,
                        "cycles_complete": 9,
                        "frequency": 3,
                        "run_date": "2020-07-04T00:00:00+02:00",
                        "status": 1,
                        "status_reason": "",
                        "status_text": "ACTIVE",
                        "token": "a3b3ae55-ab8b-b388-df23-4e6882b86ce0"
                    }
                }
            }

        Example response of a tokenized subscription:

        .. code-block::

            {
                "code": 200,
                "status": "success",
                "data": {
                    "response": {
                        "status": 1,
                        "status_reason": "",
                        "status_text": "ACTIVE"
                    }
                }
            }

        :rtype: Subscription
        """
        uri = urljoin([self.uri, token, 'fetch'])
        response = self.request('GET', uri)
        data = response.payload
        if isinstance(data, dict):
            if 'token' not in data:
                data['token'] = token
            sub_type = constants.SubscriptionType.TOKENIZATION.value
            if 'frequency' in data:
                sub_type = constants.SubscriptionType.REGULAR.value
            data['subscription_type'] = sub_type

        if self.is_card:
            return Card(data)
        return Subscription(data)


    def cancel(self, token):
        """
        PUT /subscriptions/:token/cancel

        If the subscription is already cancelled::

            {
                "code": 400,
                "status": "failed",
                "data": {
                    "response": false,
                    "message": "Failure - The subscription status is cancelled"
                }
            }

        :rtype: bool
        """
        uri = urljoin([self.uri, token, 'cancel'])
        # TODO: handle "Failure - The subscription status is cancelled"
        response = self.request('PUT', uri, raise_for_status=False)
        if not response.ok:
            cancel_msg = 'failure - the subscription status is cancelled'
            if cancel_msg in response.message.lower():
                # This would be a 400 status which is why we have to set
                # raise_for_status to False. Override the values, because
                # this subscription has already been cancelled so everything
                # is okay.
                #
                # TODO REVIEW:
                # Perhaps add a flag to the cancel method to raise an exception
                # for this. However, this will be the default behaviour.
                response.ok = True
                response.code = 200
                if response.payload is False:
                    response.payload = True
            else:
                raise PayFastAPIException(response)
        data = response.payload
        cache_bust(token)
        return data


    def update_card_link(self, token, return_url=None) -> str:
        """
        This doesn't point to the PayFast API but it still fits here.
        """
        host = settings.PAYFAST_HOST
        uri = f'https://{host}/eng/recurring/update/{token}'
        if return_url:
            uri = f'{uri}?return={return_url}'
        return uri




class Subscriptions(SubscriptionBaseResource, Resource):


    def pause(self, token):
        """
        PUT /subscriptions/:token/pause

        :rtype: bool
        """
        uri = urljoin([self.uri, token, 'pause'])
        response = self.request('PUT', uri)
        data = response.payload
        cache_bust(token)
        return data


    def unpause(self, token):
        """
        PUT /subscriptions/:token/unpause

        :rtype: bool
        """
        uri = urljoin([self.uri, token, 'unpause'])
        response = self.request('PUT', uri)
        data = response.payload
        cache_bust(token)
        return data


    def update(
        self,
        token,
        cycles: int=None,
        run_date: datetime=None,
        amount_cents: int=None,
        amount=None,
    ):
        """
        PATCH /subscriptions/:token/update

        :param cycles: The number of cycles for the subscription.
        :param run_date: The next run date for the subscription.
        :param amount_cents: The amount which the buyer must pay, in cents (ZAR).
        :param amount: The amount which the buyer must pay. Either provide
                       this or ``amount_cents``.

        .. note::

            You cannot update the "frequency" of a subscription.
            This is because we would have no way of knowing the start
            date of the subscription if we allow the frequency to change.

        Example response from API:

        .. code-block::

            {
                "code": 200,
                "status": "success",
                "data": {
                    "response": {
                        "token": "a3b3ae55-ab8b-b388-df23-4e6882b86ce0",
                        "amount": 1628,
                        "cycles": 14,
                        "cycles_complete": 9,
                        "frequency": 3,
                        "status": 1,
                        "run_date": "2016-07-04"
                    }
                }
            }
        """
        from payfast import callbacks

        uri = urljoin([self.uri, token, 'update'])
        payload = {}
        if cycles:
            payload['cycles'] = cycles
        if run_date:
            if not isinstance(run_date, datetime):
                raise ValueError('"run_date" must be a datetime object.')
            run_date = timezone.normalize(run_date)
            run_date = run_date.strftime('%Y-%m-%d')
            payload['run_date'] = run_date

        if not amount_cents and not amount:
            raise ValueError(
                'You must provide a value for either "amount" or "amount_cents" '
                'when running "Subscriptions.update".'
            )
        if amount:
            try:
                amount = Decimal(amount)
                amount = amount.quantize(Decimal('1.00'))
            except (decimal.InvalidOperation, TypeError):
                amount_type = type(amount)
                raise ValueError(
                    f'Value provided for "amount" argument ("{amount}") '
                    f'must support conversion to "Decimal". '
                    f'Value type: "{amount_type}".'
                )
            amount_cents = amount * Decimal(100)

        amount_cents = int(amount_cents)
        payload['amount'] = amount_cents
        if not payload:
            raise ValueError(
                'You must provide at least one of the optional kwargs for the '
                'subscription update.'
            )
        response = None
        try:
            response = self.request('PATCH', uri, payload=payload)
        except Exception as exc:
            callbacks._subscription_update(token, payload, success=False)
            raise
        data = response.payload
        cache_bust(token)
        callbacks._subscription_update(token, payload, success=True)
        return data


    def new(self, *args, **kwargs):
        return SubscriptionPayment(*args, **kwargs)




class Cards(SubscriptionBaseResource, Resource):


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_card = True


    def charge(
        self,
        token,
        amount: Decimal,
        item_name,
        item_description=None,
        itn: bool=True, # TODO possibly change to send_itn
        m_payment_id=None,
        cc_cvv: str=None,
        setup=None,
    ):
        """
        POST /subscriptions/:token/adhoc

        Charge a tokenization payment based on the token provided.

        Example response::

            {
                "code": 200,
                "status": "success",
                "data": {
                    "response": true,
                    "message": "Transaction was successful(00)",
                    "pf_payment_id": "1324567"
                }
            }

        Another example::

            {
                "code": 400,
                "status": "failed",
                "data": {
                    "response": 4,
                    "message": "The subscription is not in a valid state."
                }
            }
        """
        amount_cents = int(amount * 100)
        logger.info(f'Charging card "{token}" with {amount_cents} cents.')
        uri = urljoin([self.uri, token, 'adhoc'])
        if itn:
            itn = 'true'
        else:
            itn = 'false'
        _payload = {
            'amount': amount_cents,
            'item_name': item_name,
            'item_description': item_description,
            'itn': itn,
            'm_payment_id': m_payment_id,
            'cc_cvv': cc_cvv,
            'setup': setup,
        }
        payload = {
            key: value for key, value in _payload.items() if value is not None
        }
        response = self.request('POST', uri, payload=payload)
        pf_payment_id = None
        data = getattr(response, 'payload')
        try:
            pf_payment_id = data['pf_payment_id']
        except (KeyError, TypeError):
            # No errors were raised in making the request so let's assume
            # the charge was successful. Log this for someone to look at
            # and figure out what happened otherwise there may be a risk
            # in double-charging if the user of this library retries payment.
            logger.error(
                f'No PayFast payment ID was found in response payload. '
                f'Payload: {data}'
            )
        return pf_payment_id


    def new(self, *args, **kwargs):
        return TokenizedPayment(*args, **kwargs)
