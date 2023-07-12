import uuid
import json
from decimal import Decimal

from payfast.itn import ITN




def test_itn():
    upgrade_to_id = str(uuid.uuid4())
    metadata = {
        'user_id': '456',
    }
    data = {
        'm_payment_id': 'SuperUnique1',
        'pf_payment_id': '1089250',
        'payment_status': 'COMPLETE',
        'item_name': 'test+product',
        'item_description': 'test+description' ,
        'amount_gross': 200.00,
        'amount_fee': -4.60,
        'amount_net': 195.40,
        'custom_str1': json.dumps(metadata),
        'custom_str2': '',
        'custom_str3': '',
        'custom_str4': '',
        'custom_str5': '',
        'custom_int1': '123',
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
    itn = ITN(data)

    assert itn.pf_payment_id == data['pf_payment_id']
    assert itn.payment_status == data['payment_status']
    assert itn.item_name == data['item_name']
    assert itn.merchant_id == data['merchant_id']
    assert itn.amount_gross == Decimal(data['amount_gross']).quantize(Decimal('1.00'))
    assert itn.amount_fee == Decimal(data['amount_fee']*-1).quantize(Decimal('1.00'))
    assert itn.amount_net == Decimal(data['amount_net']).quantize(Decimal('1.00'))
    assert itn.signature == data['signature']
    assert itn.user_id ==  metadata.get('user_id')
