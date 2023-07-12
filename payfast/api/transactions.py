import json
import decimal
import logging
from decimal import Decimal
from datetime import datetime
from typing import List

from payfast import constants, timezone
from payfast.base import Resource
from payfast.utils import urljoin, csv_to_dict
from payfast.conf import settings
from payfast.exceptions import PayFastAPIException
from payfast.payment import (
    Payment,
    SubscriptionPayment,
    TokenizedPayment,
)

logger = logging.getLogger('payfast.api')





class Transaction:

    def __init__(self, data: dict):
        fields = [
            'date',
            'type',
            'sign',
            'party',
            'name',
            'description',
            'currency',
            'funding_type',
            'batch_id',
            'gross',
            'fee',
            'net',
            'balance',
            'm_payment_id',
            'pf_payment_id',
            'custom_str1',
            'custom_int1',
            'custom_str2',
            'custom_int2',
            'custom_str3',
            'custom_str4',
            'custom_str5',
            'custom_int3',
            'custom_int4',
            'custom_int5',
        ]
        for field in fields:
            setattr(self, field, None)
        for key, value in data.items():
            setattr(self, key, value)




class TransactionList:

    def __init__(self, data: list):
        """
        Example of data argument::

            [
                {
                    "date": "2023-06-08 06:19:09",
                    "type": "FUNDS_RECEIVED",
                    "sign": "CREDIT",
                    "party": "John Smith",
                    "name": "Test plan",
                    "description": "Standard",
                    "currency": "ZAR",
                    "funding_type": "CC",
                    "batch_id": "",
                    "gross": "10.00",
                    "fee": "-2.67",
                    "net": "7.33",
                    "balance": "9.85",
                    "m_payment_id": "123",
                    "pf_payment_id": "123456789",
                    "custom_str1": "",
                    "custom_int1": "",
                    "custom_str2": "",
                    "custom_int2": "",
                    "custom_str3": "",
                    "custom_str4": "",
                    "custom_str5": "",
                    "custom_int3": "",
                    "custom_int4": "",
                    "custom_int5": ""
                }
            ]
        """
        self.all = []
        self.data = data
        for data in data:
            transaction = Transaction(data)
            self.all.append(transaction)


    def __iter__(self):
        return iter(self.all)


    def asc(self):
        """
        Earliest first.
        """
        data = sorted(
            self.all,
            key=lambda x: datetime.strptime(x.date, '%Y-%m-%d %H:%M:%S'),
        )
        return data


    def desc(self):
        """
        Latest first.
        """
        data = sorted(
            self.all,
            key=lambda x: datetime.strptime(x.date, '%Y-%m-%d %H:%M:%S'),
            reverse=True,
        )
        return data




class Transactions(Resource):

    key = 'transactions/history'


    def _prep_params(self, params):
        _params = {}
        for key, value in params.items():
            if not isinstance(value, datetime):
                continue
            if key in ['from', 'to', 'date']:
                value = value.strftime('%Y-%m-%d')
            _params[key] = value
        return _params


    def _normalize_response(self, csv_string):
        data = csv_to_dict(csv_string)
        if not isinstance(data, list):
            data = [data]
        _data = []
        for item in data:
            d = {}
            for key, value in item.items():
                key = key.lower()
                key = key.replace(' ', '_')
                if key in ['gross', 'fee', 'net', 'balance']:
                    try:
                        value = Decimal(value)
                    except decimal.InvalidOperation:
                        # logger.warning(f"Error converting {key} with value {repr(value)} to Decimal")
                        continue
                    value = value.quantize(Decimal('1.00'))
                d[key] = value
            _data.append(d)
        return _data


    def list(self, start: datetime, end: datetime):
        """
        GET /transactions/history?from=:date&to=:date
        """
        params = self._prep_params({
            'from': start,
            'to': end,
        })
        response = self.request('GET', self.uri, params=params)
        csv_string = response.payload
        data = self._normalize_response(csv_string)
        return TransactionList(data)


    def list_daily(self, date: datetime):
        """
        GET /transactions/history/daily?date=:date
        """
        uri = urljoin([
            self.uri,
            constants.TransactionPeriod.DAILY.value,
        ])
        params = self._prep_params({
            'date': date.strftime('%Y-%m-%d'),
        })
        response = self.request('GET', uri, params=params)
        csv_string = response.payload
        data = self._normalize_response(csv_string)
        return TransactionList(data)


    def list_weekly(self, date: datetime):
        """
        GET /transactions/history/weekly?date=:date
        """
        uri = urljoin([
            self.uri,
            constants.TransactionPeriod.WEEKLY.value,
        ])
        params = self._prep_params({
            'date': date.strftime('%Y-%m-%d'),
        })
        response = self.request('GET', uri, params=params)
        csv_string = response.payload
        data = self._normalize_response(csv_string)
        return TransactionList(data)


    def list_monthly(self, date: datetime):
        """
        GET /transactions/history/monthly?date=:date
        """
        uri = urljoin([
            self.uri,
            constants.TransactionPeriod.MONTHLY.value,
        ])
        params = self._prep_params({
            'date': date.strftime('%Y-%m'),
        })
        response = self.request('GET', uri, params=params)
        csv_string = response.payload
        data = self._normalize_response(csv_string)
        return TransactionList(data)




class CCTransaction:

    def __init__(self, data):
        self.pf_payment_id = data.get('pf_payment_id', None)
        self.m_payment_id = data.get('m_payment_id', None)
        self.status = data.get('status', None)

        # PayFast returns the amount in cents.
        # Convert it to something more obvious.
        self.amount_cents = int(data.get('amount', None))
        self.amount = Decimal(self.amount_cents) / Decimal(100)
        self.amount = self.amount.quantize(Decimal('1.00'))

        self.cc_status = data.get('cc_status', None)
        self.cc_message = data.get('cc_message', None)




class CCTransactions(Resource):

    key = 'process/query'


    def get(self, id: str):
        """
        GET /process/query/:id

        Queries credit card transactions only.

        https://api.payfast.co.za/process/query/01d2e4c7-28c8-3a86-151f-eab5357da649
        https://api.payfast.co.za/process/query/69

        Example response::

            {
                "code": 200,
                "status": "success",
                "data": {
                    "response": {
                        "pf_payment_id": 69,
                        "m_payment_id": 232345,
                        "status": "COMPLETE",
                        "amount": 3600,
                        "cc_status": "00",
                        "cc_message": "Approved or completed successfully (00)"
                    },
                    "message": "Success"
                }
            }
        """
        uri = urljoin([self.uri, id])
        response = self.request('GET', uri)
        data = response.payload
        return CCTransaction(data)
