from payfast import PayFast, timezone, constants
from payfast.exceptions import PayFastAPIException

pf = PayFast()




def test_form():
    payment = pf.payment(10.00, 'Some things')
    rendered = payment.get_form()




def test_subscription_form():
    payment = pf.subscription(
        10.00,
        'Some things, but every month',
        frequency=constants.Frequency.MONTHLY.value,
    )
    rendered = payment.get_form()
