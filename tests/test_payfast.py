import uuid
import json
import logging

from payfast import PayFast, constants, timezone
from payfast.exceptions import PayFastAPIException
from payfast.payment import (
    Payment,
    SubscriptionPayment,
)
from payfast.itn import ITN

pf = PayFast()




def test_ping():
    # pf.ping()
    pass
