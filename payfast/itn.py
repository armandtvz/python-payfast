import json
import decimal
from decimal import Decimal
from datetime import datetime

from payfast import PayFast
from payfast import constants, timezone, callbacks
from payfast import security_checks as checks
from payfast.exceptions import PayFastAPIException
from payfast.serialization import decoder
from payfast.api.subscriptions import Upgrade

payfast = PayFast()




class ITN:
    """
    A PayFast ITN aka "instant transaction notification".
    """

    def __init__(self, data, payfast_ipaddr=None):
        """
        Example of what PayFast might send in the ITN webhook::

            itn = {
                'm_payment_id': '789',
                'pf_payment_id': '1089250',
                'payment_status': 'COMPLETE',
                'item_name': 'Test plan',
                'item_description': 'Gold package',
                'amount_gross': 200.00,
                'amount_fee': -4.60,
                'amount_net': 195.40,
                'custom_str1': '', # Reserved for python-payfast JSON metadata.
                'custom_str2': '',
                'custom_str3': '',
                'custom_str4': '',
                'custom_str5': '',
                'custom_int1': '',
                'custom_int2': '',
                'custom_int3': '',
                'custom_int4': '',
                'custom_int5': '',
                'name_first': '',
                'name_last': '',
                'email_address': '',
                'merchant_id': '10000100',
                'signature': 'ad8e7685c9522c24365d7ccea8cb3db7',
            }
        """
        self.payload = data
        self.data_from_payfast = json.dumps(data)
        self.payfast_ipaddr = payfast_ipaddr
        self.paid_at = timezone.now()
        self.sub = None
        self.secchecks_passed = None
        self.secchecks_results = None

        self.is_upgrade = False
        self.upgrade = None

        required = [
            'pf_payment_id',
            'payment_status',
            'merchant_id',
            # Commented-out on purpose. PayFast doesn't returns a blank string
            # for "item_name" for free trial subscriptions.
            # 'item_name',
        ]
        integer_fields = [
            'custom_int1',
            'custom_int2',
            'custom_int3',
            'custom_int4',
            'custom_int5',
        ]
        decimal_fields = [
            'amount_gross',
            'amount_fee',
            'amount_net',
        ]
        # Transaction details
        self.pf_payment_id = data.get('pf_payment_id', None)
        self.payment_status = data.get('payment_status', None)
        self.item_name = data.get('item_name', None)

        self.item_description = data.get('item_description', None)
        self.m_payment_id = data.get('m_payment_id', None)
        if self.m_payment_id:
            self.m_payment_id = str(self.m_payment_id)

        self.amount_gross = data.get('amount_gross', None)
        self.amount = self.amount_gross
        self.amount_fee = data.get('amount_fee', None)
        self.amount_net = data.get('amount_net', None)

        self.custom_str1 = data.get('custom_str1', None) # Reserved for general
        self.custom_str2 = data.get('custom_str2', None) # Reserved for upgrade
        self.custom_str3 = data.get('custom_str3', None)
        self.custom_str4 = data.get('custom_str4', None)
        self.custom_str5 = data.get('custom_str5', None)

        self.custom_int1 = data.get('custom_int1', None)
        self.custom_int2 = data.get('custom_int2', None)
        self.custom_int3 = data.get('custom_int3', None)
        self.custom_int4 = data.get('custom_int4', None)
        self.custom_int5 = data.get('custom_int5', None)

        # Customer details
        self.name_first = data.get('name_first', None)
        self.name_last = data.get('name_last', None)
        self.email_address = data.get('email_address', None)

        # Merchant details
        self.merchant_id = data.get('merchant_id', None)

        # Recurring billing details
        self.token = data.get('token', None)
        self.billing_date = data.get('billing_date', None)
        try:
            self.billing_date = datetime.strptime(self.billing_date, '%Y-%m-%d')
            self.billing_date = timezone.normalize(self.billing_date)
        except (ValueError, TypeError):
            # ValueError: time data '' does not match format '%Y-%m-%d'
            # TypeError: strptime() argument 1 must be str, not None
            # TODO: Perhaps log this if ValueError
            self.billing_date = None

        # Security information
        self.signature = data.get('signature', None)

        for field in decimal_fields:
            value = getattr(self, field, None)
            try:
                value = Decimal(value)
                value = value.quantize(Decimal('1.00'))
            except (TypeError, decimal.InvalidOperation):
                value = None
            setattr(self, field, value)

        for field in integer_fields:
            value = getattr(self, field, None)
            try:
                value = int(value)
            except (ValueError, TypeError):
                value = None
            setattr(self, field, value)

        # TODO REVIEW: this is unlikely to happen
        missing_values = set()
        for field in required:
            value = getattr(self, field, None)
            if not value:
                if isinstance(value, int):
                    if value == 0:
                        continue
                missing_values.add(field)
        missing_values = list(missing_values)
        if missing_values:
            # It was found that PayFast does not return "item_name" for
            # subscriptions that are free trials:
            # {
            #     'item_name': '',
            #     ...
            # }
            raise ValueError(
                f'The following values are required for the PayFast ITN object: '
                f'{missing_values}'
            )

        if self.amount_fee:
            if self.amount_fee < 0:
                self.amount_fee = abs(self.amount_fee)

        self.expected_amount = callbacks._get_expected_amount(self.m_payment_id)
        self.sub = self.get_subscription()

        self.handle_custom_str1()
        self.handle_custom_str2()


    def handle_custom_str1(self):
        from payfast.payment import Payment

        # custom_str1 is reserved for metadata.
        # See ``Payment`` for more info.
        str1 = self.custom_str1
        if not str1:
            return

        try:
            str1 = json.loads(str1, object_hook=decoder)
        except (json.decoder.JSONDecodeError, TypeError):
            return

        for field in Payment.custom_str1_fields:
            value = str1.get(field, None)
            setattr(self, field, value)


    def handle_custom_str2(self):
        str2 = self.custom_str2
        self.is_upgrade = False
        if not str2:
            return
        self.plan_id = None
        self.upgrade_to_id = None
        self.is_upgrade = True

        try:
            str2 = json.loads(str2, object_hook=decoder)
        except (json.decoder.JSONDecodeError, TypeError):
            return

        upgrade_from_token = str2.get('token', None)
        if not upgrade_from_token:
            return # TODO REVIEW

        cancel = str2.get('cancel', False)

        sub = None
        try:
            sub = payfast.subs.get(upgrade_from_token)
        except PayFastAPIException:
            return # TODO REVIEW

        amount = str2.get('amount', None)
        item_name = str2.get('item_name', None)
        self.plan_id = str2.get('plan_id', None)
        self.upgrade_to_id = str2.get('upgrade_to_id', None)

        kwargs = {
            'plan_id': self.plan_id,
            'upgrade_to_id': self.upgrade_to_id,
            'cancel': cancel,
        }
        self.upgrade = Upgrade(
            sub,
            amount,
            item_name,
            **kwargs,
        )


    @property
    def is_for_subscription(self):
        if self.token:
            return True
        return False


    @property
    def is_paid(self):
        if self.payment_status == constants.PaymentStatus.COMPLETE.value:
            return True
        return False


    @property
    def is_complete(self):
        return self.is_paid


    @property
    def is_success(self):
        return self.is_paid


    @property
    def is_cancelled(self):
        return not self.is_paid


    @property
    def status(self):
        return self.payment_status


    def get_subscription(self):
        if not self.token:
            return

        if self.sub:
            return self.sub

        # This is a payment for a subscription/tokenized subscription.
        # This could be one of four things:
        # - This could be when a user starts a new subscription.
        # - It might also be PayFast billing them automatically.
        #
        # Or:
        # - It might be when a user starts a new tokenized subscription.
        # - It might be a tokenized payment automatically initiated by
        #   the merchant.
        try:
            self.sub = payfast.subscriptions.get(self.token)
        except PayFastAPIException:
            # TODO REVIEW
            raise
        return self.sub


    def get_sub(self, *args, **kwargs):
        """
        An alias for ``get_subscription``.
        """
        return self.get_subscription(*args, **kwargs)


    def get_user(self):
        try:
            import django
            from django.contrib.auth import get_user_model
        except ImportError:
            return
        User = get_user_model()
        if not self.user_id:
            return
        user = None
        try:
            user = User.objects.get(pk=self.user_id)
        except User.DoesNotExist:
            pass
        return user


    def is_downgrade(self):
        return not self.is_upgrade


    def do_security_checks(self):
        if self.secchecks_passed and self.secchecks_results:
            return self.secchecks_passed, self.secchecks_results

        passed = False
        results = {}

        check_one = None
        check_two = None
        check_three = None
        check_four = None

        # Security check 1:
        # Verify the signature.
        check_one = checks.signature_is_valid(self.signature, self.payload)

        # Security check 2:
        # Check that the notification has come from a valid PayFast domain.
        if self.payfast_ipaddr:
            check_two, payfast_ip_address = checks.request_is_from_payfast(
                self.payfast_ipaddr,
            )

        # Security check 3:
        # Compare payment data.
        if self.expected_amount:
            check_three = checks.payment_data_is_valid(
                total=self.expected_amount,
                amount_gross=self.amount_gross,
            )

        # Security check 4:
        # Perform a server request to confirm the details.
        check_four = checks.send_validation_request(self.payload)

        if (
            check_one
            and check_two
            and check_three
            and check_four
        ):
            # Successful payment.
            passed = True
        else:
            # According to PayFast:
            # Check payment manually and log for investigation.
            passed = False

        # TODO REVIEW
        results = {
            'security_checks': {
                'check_one': check_one,
                'check_two': check_two,
                'check_three': check_three,
                'check_four': check_four,
            },
        }
        self.secchecks_passed = passed
        self.secchecks_results = results
        return passed, results
