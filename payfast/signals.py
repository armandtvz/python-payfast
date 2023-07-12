"""
Usage:

from payfast.signals import payment_done
payment_done.connect(my_callback, dispatch_uid='my_unique_id')
"""

try:
    from django.dispatch import Signal
except ImportError:
    Signal = None


payment_start = None
payment_done = None
subscription_update = None
if Signal:
    payment_start = Signal()
    payment_done = Signal()
    subscription_update = Signal()
