try:
    import django
except ImportError:
    django = None
    signals = None
else:
    from payfast import signals

from decimal import Decimal

from payfast import PayFast
from payfast.conf import settings




def _payment_done(itn) -> list:
    """
    The callback that must be called when a payment is done.
    This does not imply success or that the security checks
    passed. The plain callback configured is preferred over
    using the Django signal.
    """
    responses = []
    callback = settings.payment_done_callback
    if callback:
        # Don't handle exceptions here
        result = callback(itn)
        # Normalize the result to look like the responses returned by Django
        # from signal receivers.
        responses = [(callback, result),]

    elif django:
        signal = signals.payment_done
        # No need to use Django's Signal.send_robust here
        responses = signal.send(sender=PayFast, itn=itn)
    return responses




def _payment_start(payment) -> list:
    """
    The callback that must be called when a payment is initialized.
    """
    responses = []
    callback = settings.payment_start_callback
    if callback:
        # Don't handle exceptions here
        result = callback(payment)
        responses = [(callback, result),]

    elif django:
        signal = signals.payment_start
        # No need to use Django's Signal.send_robust here
        responses = signal.send(sender=PayFast, pf_payment=payment)
    return responses




def _subscription_update(token, payload, success=True) -> list:
    """
    Called when a subscription is updated.
    """
    responses = []
    callback = settings.subscription_update_callback
    if callback:
        # Don't handle exceptions here
        result = callback(token, payload, success)
        responses = [(callback, result),]

    elif django:
        signal = signals.subscription_update
        # No need to use Django's Signal.send_robust here
        responses = signal.send(
            sender=PayFast,
            token=token,
            payload=payload,
            success=success
        )
    return responses




# TODO REVIEW
def _get_expected_amount(m_payment_id):
    """
    For the ITN security checks to complete we need to get the amount
    that was expected for a transaction/payment. The ``m_payment_id``
    is likely the primary key of a row in a database that also stores
    the amount.
    """
    amount = None
    callback = settings.expected_amount_callback
    if callback:
        amount = callback(m_payment_id)
        amount = Decimal(amount)
    return amount
