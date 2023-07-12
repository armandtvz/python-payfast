from decimal import Decimal
from typing import Optional, Union
from datetime import datetime

import pydantic as dantic
from pydantic import constr, conint

from payfast import constants




class PaymentValidator(dantic.BaseModel):

    amount: str
    item_name: str
    m_payment_id: str = None
    item_description: str = None

    merchant_id: int = None
    merchant_key: dantic.SecretStr = None
    # return_url: Optional[dantic.AnyHttpUrl] = None
    # cancel_url: Optional[dantic.AnyHttpUrl] = None
    # notify_url: Optional[dantic.AnyHttpUrl] = None
    return_url: str = None
    cancel_url: str = None
    notify_url: str = None

    name_first: str = None
    name_last: str = None
    email_address: str = None
    cell_number: str = None

    custom_int1: int = None
    custom_int2: int = None
    custom_int3: int = None
    custom_int4: int = None
    custom_int5: int = None

    custom_str1: constr(max_length=255) = None
    custom_str2: constr(max_length=255) = None
    custom_str3: constr(max_length=255) = None
    custom_str4: constr(max_length=255) = None
    custom_str5: constr(max_length=255) = None

    email_confirmation: Union[conint(ge=0, le=1), bool] = None
    confirmation_address: str = None
    payment_method: constants.PaymentMethod

    signature: constr(min_length=32, max_length=32)




class SubscriptionPaymentValidator(PaymentValidator):
    frequency: constants.Frequency
    cycles: conint(ge=0)
    subscription_type: constants.SubscriptionType

    billing_date: Union[str, datetime] = None
    recurring_amount: str = None
