import hashlib
import logging
from decimal import Decimal
from ipaddress import ip_network, ip_address

import requests

from payfast.conf import settings
from payfast.signature import make_signature, make_querystring




def signature_is_valid(posted_signature, payfast_data):
    querystring = make_querystring(payfast_data)
    signature = hashlib.md5(querystring.encode()).hexdigest()
    if posted_signature == signature:
        return True
    return False




def request_is_from_payfast(ip_string):
    """
    Check that the notification has come from a valid PayFast domain.
    """
    valid_networks = settings.PAYFAST_NETWORKS
    valid_ips = settings.PAYFAST_IP_LIST
    try:
        ip = ip_address(ip_string)
    except ValueError:
        # ValueError: <value> does not appear to be an IPv4 or IPv6 address
        # We are unable to determine whether or not the request is from
        # PayFast. Play it safe and return False.
        return False, ip

    if ip in valid_ips:
        return True, ip
    for net in valid_networks:
        if ip in net:
            return True, ip
    return False, ip




def payment_data_is_valid(total, amount_gross):
    """
    The amount you expected the customer to pay should match the
    ``amount_gross`` value sent in the notification.
    """
    amount = amount_gross
    if total is None or amount is None:
        return False

    total = Decimal(total)
    amount = Decimal(amount)
    magnitude = abs(total - amount)

    if magnitude < 0.01:
        return True
    return False




def send_validation_request(payfast_data):
    """
    Validate the data received from PayFast by contacting the PayFast server
    to confirm the order details.
    """
    url = settings.VALIDATE_URL
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    querystring = make_querystring(payfast_data)
    response = requests.post(url, data=querystring, headers=headers)
    if response.text == 'VALID':
        logging.info('Got "VALID" response text from PayFast for security check.')
        return True
    return False
