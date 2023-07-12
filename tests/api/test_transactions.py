from payfast import PayFast, timezone
from payfast.exceptions import PayFastAPIException

pf = PayFast()




def test_cc_transactions():
    id = '123456789'
    try:
        transaction = pf.cc_transactions.get(id)
    except PayFastAPIException:
        pass




def test_transactions():
    transactions = pf.transactions.list(
        start=timezone.one_week_ago(),
        end=timezone.now(),
    )
    pf.transactions.list_daily(date=timezone.now())
    pf.transactions.list_weekly(date=timezone.now())
    pf.transactions.list_monthly(date=timezone.now())
