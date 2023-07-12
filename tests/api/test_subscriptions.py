import uuid

from payfast import PayFast, timezone
from payfast.exceptions import PayFastAPIException

pf = PayFast()




def test_subscription():
    id = '123456789'
    try:
        transaction = pf.cc_transactions.get(id)
    except PayFastAPIException:
        pass




def test_subscriptions():
    token = str(uuid.uuid4())
    try:
        subscription = pf.subscriptions.get(token)
    except PayFastAPIException:
        pass
