from enum import Enum
from decimal import Decimal




# PayFast does not allow payments smaller than 5.00 Rand (ZAR).
PAYFAST_MIN_AMOUNT = Decimal(5)

# FUTURE: Later, we can have a user-defined minimum amount.
MIN_AMOUNT = PAYFAST_MIN_AMOUNT




class Frequency(Enum):
    DAILY = 1
    WEEKLY = 2
    MONTHLY = 3
    QUARTERLY = 4
    BIANNUALLY = 5
    ANNUAL = 6

    YEARLY = 6




class SubscriptionType(Enum):
    REGULAR = 1
    TOKENIZATION = 2




class SubscriptionStatus(Enum):
    ACTIVE = 'ACTIVE'
    CANCELLED = 'CANCELLED'




class PaymentMethod(Enum):
    EFT = 'eft'
    CREDIT_CARD = 'cc'
    DEBIT_CARD = 'dc'
    MASTERPASS = 'mp'
    MOBICRED = 'mc'
    SCODE = 'sc'
    SNAPSCAN = 'ss'
    ZAPPER = 'zp'
    MORETYME = 'mt'
    STORE = 'rcs'




class Cycles(Enum):
    INDEFINITE = 0




class BooleanInteger(Enum):
    OFF = 0
    ON = 1




class PaymentStatus(Enum):
    CANCELLED = 'CANCELLED'
    COMPLETE = 'COMPLETE'
    COMPLETED = COMPLETE




class TransactionPeriod(Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'




PAYFAST_VALID_HOSTS = {
    'www.payfast.co.za',
    'w1w.payfast.co.za',
    'w2w.payfast.co.za',
    'sandbox.payfast.co.za',
}
