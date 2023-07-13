import os
from typing import Union
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from payfast.conf import settings
from payfast.payment import (
    Payment,
    SubscriptionPayment,
    TokenizedPayment,
    TokenizedSub,
)
from payfast.base import RequestsTransport
from payfast.logging import configure_logging
from payfast.exceptions import PayFastException
from payfast.api.subscriptions import Subscriptions, Cards
from payfast.api.transactions import Transactions, CCTransactions
from payfast.api.refunds import Refunds




__version__ = '0.4'
__title__ = 'python-payfast'




class PayFast:

    TRANSPORT_CLASS = RequestsTransport


    def __init__(
        self,
        base_uri=settings.API_ROOT,
        version='v1',
    ):
        configure_logging()
        self.base_uri = settings.API_ROOT
        self.api_version = version
        args = [version]
        kwargs = {'transport_class': self.TRANSPORT_CLASS}

        self.subscriptions = Subscriptions(*args, **kwargs)
        self.subs = Subscriptions(*args, **kwargs) # alias
        self.cards = Cards(*args, **kwargs)

        self.transactions = Transactions(*args, **kwargs)
        self.cc_transactions = CCTransactions(*args, **kwargs)

        self.refunds = Refunds(*args, **kwargs)
        self.refund = self.refunds.create # alias

        self.payment = Payment
        self.subscription = SubscriptionPayment
        self.sub = SubscriptionPayment # alias
        self.tokenized_sub = TokenizedSub
        self.tsub = TokenizedSub # alias
        self.tokenized = TokenizedPayment


    def ping(self):
        from payfast.utils import urljoin
        uri = urljoin([self.base_uri, 'ping'])
        Transport = self.TRANSPORT_CLASS
        transport = Transport(self.api_version)
        response = transport.request('GET', uri)
        expected = 'PayFast API'
        if settings.DEBUG:
            expected = 'API V1'
        if response in expected:
            return True
        return False


    def trial(
        self,
        amount,
        item_name,
        is_tokenized=False,
        **kwargs
    ):
        zero_amount = 0
        payment = None
        kwargs['recurring_amount'] = amount
        sub = self.sub
        if is_tokenized:
            sub = self.tsub
        payment = sub(
            zero_amount,
            item_name,
            **kwargs,
        )
        return payment
