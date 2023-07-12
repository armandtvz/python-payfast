import json
import logging
from functools import wraps
from datetime import timedelta

try:
    from rest_framework import status
    from rest_framework.views import APIView
    from rest_framework.response import Response

    from django.shortcuts import render
    from django.http import Http404
    from django.conf import settings as django_settings

except ImportError:
    status = None
    APIView = None
    Response = None

    render = None
    Http404 = None
    django_settings = None

from payfast import PayFast, constants, callbacks
from payfast.utils import get_ip
from payfast.conf import settings
from payfast.itn import ITN

payfast = PayFast()
logger = logging.getLogger('payfast.drf')




class NotifyEndpoint(APIView):
    """
    This does not return a page. PayFast sends a POST request to this
    endpoint after a successful or cancelled payment.

    From the PayFast docs:

        The URL which is used by PayFast to post the Instant Transaction
        Notifications (ITNs) for this transaction.

        For the notify_url mentioned, a variable can be specified globally on
        the Merchant’s PayFast account or overridden on a per transaction basis.
        The value provided during a transaction overrides the global setting.

    Another extract:

        On receiving the payment notification from PayFast, return a header
        200 to prevent further retries. If no 200 response is returned the
        notification will be re-sent immediately, then after 10 minutes and
        then at exponentially longer intervals until eventually stopping.

    Expected data:

    .. code-block:: JSON

        {
            "m_payment_id": "123",
            "pf_payment_id": "1616421",
            "payment_status": "COMPLETE",
            "item_name": "",
            "item_description": "",
            "amount_gross": "0.00",
            "amount_fee": "0.00",
            "amount_net": "0.00",
            "custom_str1": "",
            "custom_str2": "",
            "custom_str3": "",
            "custom_str4": "",
            "custom_str5": "",
            "custom_int1": "",
            "custom_int2": "",
            "custom_int3": "",
            "custom_int4": "",
            "custom_int5": "",
            "name_first": "Armandt",
            "name_last": "van Zyl",
            "email_address": "armandt@example.com",
            "merchant_id": "10005195",
            "token": "07d65cf5-a124-40c8-acb8-c3d79ad7d8ec",
            "billing_date": "2023-02-09",
            "signature": "b5875978529550ec7b49440086d5f5a2"
        }
    """

    def post(self, request, format=None):
        logger.debug(json.dumps(request.data, indent=4))
        ipaddr = get_ip(request)
        itn = ITN(request.data, payfast_ipaddr=ipaddr)
        passed, security_check_results = itn.do_security_checks()

        if itn.upgrade:
            itn.upgrade.do(itn=itn)

        callbacks._payment_done(itn)
        # TODO
        # if not passed:
        #     # TODO log this
        #     # logger.warning('Security checks not passed')
        #     return Response({}, status=status.HTTP_400_BAD_REQUEST)
        return Response({}, status=status.HTTP_200_OK)




def debug_only(function):
    @wraps(function)
    def decorator(request, *args, **kwargs):
        if not django_settings.DEBUG:
            raise Http404
        return function(request, *args, **kwargs)
    return decorator




@debug_only
def cancel_endpoint(request):
    """
    From the PayFast docs:
    The URL where the user should be redirected should they choose to cancel
    their payment while on the PayFast system.
    """
    return render(request, 'payfast/cancel_url.html', {})




@debug_only
def return_endpoint(request):
    """
    From the PayFast docs:
    The URL where the user is returned to after payment has been successfully
    taken.
    """
    return render(request, 'payfast/return_url.html', {})




@debug_only
def sandbox(request):
    payment = payfast.payment(10.00, 'Things', user_id=request.user.pk)
    form = payment.get_form()
    return render(request, 'payfast/sandbox.html', {
        'form': form,
    })




@debug_only
def subscription_sandbox(request):
    item_name = 'Things, but things every month'
    payment = payfast.subscription(
        10.00,
        item_name,
        plan_id='test',
        frequency=constants.Frequency.MONTHLY.value,
        user_id=request.user.pk,
    )
    form = payment.get_form()
    return render(request, 'payfast/sandbox.html', {
        'form': form,
    })




@debug_only
def free_trial_sandbox(request):
    item_name = 'Things, but things every month'
    payment = payfast.trial(
        10.00,
        item_name,
        plan_id='test',
        user_id=request.user.pk,
        free_delta=timedelta(days=7),
        frequency=constants.Frequency.MONTHLY.value,
    )
    form = payment.get_form()
    return render(request, 'payfast/sandbox.html', {
        'form': form,
        'free_days': 7,
    })
