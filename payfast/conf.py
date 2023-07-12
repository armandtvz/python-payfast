"""
Buyer credentials:
Username: sbtu01@payfast.co.za
Password: clientpass

Exposes the following settings:

.. data:: USE_PAYFAST_SANDBOX

.. data:: PAYFAST_HOST

.. data:: MERCHANT_ID

.. data:: MERCHANT_KEY

.. data:: SALT_PASSPHRASE

.. data:: PROCESS_URL

.. data:: VALIDATE_URL

.. data:: PAYFAST_NETWORKS

.. data:: PAYFAST_IP_LIST
"""
import sys
from importlib import import_module
from importlib.util import find_spec as importlib_find

from ipaddress import ip_network, ip_address

from decouple import config




def cached_import(module_path, class_name):
    # Check whether module is loaded and fully initialized.
    if not (
        (module := sys.modules.get(module_path))
        and (spec := getattr(module, "__spec__", None))
        and getattr(spec, "_initializing", False) is False
    ):
        module = import_module(module_path)
    return getattr(module, class_name)




def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError("%s doesn't look like a module path" % dotted_path) from err

    try:
        return cached_import(module_path, class_name)
    except AttributeError as err:
        raise ImportError(
            'Module "%s" does not define a "%s" attribute/class'
            % (module_path, class_name)
        ) from err




class Settings:

    DEBUG = config('PAYFAST_DEBUG', cast=bool, default=True)
    USE_PAYFAST_SANDBOX = DEBUG

    PAYFAST_HOST = None
    PROCESS_URL = None
    if USE_PAYFAST_SANDBOX:
        PAYFAST_HOST = 'sandbox.payfast.co.za'
    else:
        PAYFAST_HOST = 'www.payfast.co.za'
    API_ROOT = 'https://api.payfast.co.za'

    # Might only be set in Django, add defaults
    MERCHANT_ID = config('PAYFAST_MERCHANT_ID', cast=int)
    MERCHANT_KEY = config('PAYFAST_MERCHANT_KEY')
    SALT_PASSPHRASE = config('PAYFAST_SALT_PASSPHRASE')

    if len(SALT_PASSPHRASE) > 32:
        raise ValueError(
            'Your PayFast "SALT_PASSPHRASE" setting must be no longer than '
            '32 characters'
        )

    if DEBUG:
        MERCHANT_ID = 10005195
        MERCHANT_KEY = 'cfd5vff7cvxpp'
        SALT_PASSPHRASE = '123456789A_bcdefgh'

    PROCESS_URL = f'https://{PAYFAST_HOST}/eng/process'
    VALIDATE_URL = f'https://{PAYFAST_HOST}/eng/query/validate'

    PAYFAST_NETWORKS_DEFAULT = [
        '197.97.145.144/28',
        '41.74.179.192/27',
    ]
    PAYFAST_IP_LIST_DEFAULT = [
        '144.126.193.139',
    ]
    PAYFAST_NETWORKS = PAYFAST_NETWORKS_DEFAULT
    PAYFAST_IP_LIST = PAYFAST_IP_LIST_DEFAULT

    payfast_networks = set()
    for network in PAYFAST_NETWORKS:
        try:
            network_obj = ip_network(network)
            payfast_networks.add(network_obj)
        except ValueError:
            raise

    payfast_ip_list = set()
    for ip in PAYFAST_IP_LIST:
        try:
            ip_obj = ip_address(ip)
            payfast_ip_list.add(ip_obj)
        except ValueError:
            raise

    PAYFAST_NETWORKS = list(payfast_networks)
    PAYFAST_IP_LIST = list(payfast_ip_list)

    PAYFAST_UPDATE_BUG = config('PAYFAST_UPDATE_BUG', cast=bool, default=True)

    API_TIMEOUT = config('PAYFAST_API_TIMEOUT', cast=int, default=30)

    RETURN_URL = config('PAYFAST_RETURN_URL', default='')
    CANCEL_URL = config('PAYFAST_CANCEL_URL', default='')
    NOTIFY_URL = config('PAYFAST_NOTIFY_URL', default='')

    """
    # Follow Django convention with regard to the cache timeout
    timeout = settings.CACHE_TIMEOUT
    if timeout is None:
        # Don't expire the keys ever.
        pass

    elif timeout == 0:
        # Expire the keys immediately.
        pass
    """
    CACHE_TIMEOUT = config('PAYFAST_CACHE_TIMEOUT', cast=int, default=300)
    CACHE_KEY_PREFIX = config('PAYFAST_CACHE_KEY_PREFIX', default='payfast')

    GRACE_PERIOD_DAYS = config('PAYFAST_GRACE_PERIOD_DAYS', cast=int, default=7)
    if GRACE_PERIOD_DAYS < 6:
        raise ValueError('"GRACE_PERIOD_DAYS" must be an integer bigger than 5.')

    expected_amount_callback = config('PAYFAST_EXPECTED_AMOUNT_CALLBACK', default=None)
    if expected_amount_callback:
        expected_amount_callback = import_string(expected_amount_callback)
        if not callable(expected_amount_callback):
            raise ValueError('"expected_amount_callback" must be a callable')

    payment_done_callback = config('PAYFAST_PAYMENT_DONE_CALLBACK', default=None)
    if payment_done_callback:
        payment_done_callback = import_string(payment_done_callback)
        if not callable(payment_done_callback):
            raise ValueError('"payment_done_callback" must be a callable')

    payment_start_callback = config('PAYFAST_PAYMENT_START_CALLBACK', default=None)
    if payment_start_callback:
        payment_start_callback = import_string(payment_start_callback)
        if not callable(payment_start_callback):
            raise ValueError('"payment_start_callback" must be a callable')

    subscription_update_callback = config('PAYFAST_SUBSCRIPTION_UPDATE_CALLBACK', default=None)
    if subscription_update_callback:
        subscription_update_callback = import_string(subscription_update_callback)
        if not callable(subscription_update_callback):
            raise ValueError('"subscription_update_callback" must be a callable')


    @classmethod
    def configure_django(cls):
        dj = None
        try:
            from django.conf import settings as dj
        except ImportError:
            return
        dj.PAYFAST_DEBUG = getattr(
            dj, 'PAYFAST_DEBUG', cls.DEBUG
        )
        dj.PAYFAST_MERCHANT_ID = int(getattr(
            dj, 'PAYFAST_MERCHANT_ID', cls.MERCHANT_ID
        ))
        dj.PAYFAST_MERCHANT_KEY = getattr(
            dj, 'PAYFAST_MERCHANT_KEY', cls.MERCHANT_KEY
        )
        dj.PAYFAST_SALT_PASSPHRASE = getattr(
            dj, 'PAYFAST_SALT_PASSPHRASE', cls.SALT_PASSPHRASE
        )
        dj.PAYFAST_API_TIMEOUT = getattr(
            dj, 'PAYFAST_API_TIMEOUT', cls.API_TIMEOUT
        )
        dj.PAYFAST_EXPECTED_AMOUNT_CALLBACK = getattr(
            dj, 'PAYFAST_EXPECTED_AMOUNT_CALLBACK', cls.expected_amount_callback
        )
        dj.PAYFAST_RETURN_URL = getattr(
            dj, 'PAYFAST_RETURN_URL', cls.RETURN_URL
        )
        dj.PAYFAST_CANCEL_URL = getattr(
            dj, 'PAYFAST_CANCEL_URL', cls.CANCEL_URL
        )
        dj.PAYFAST_NOTIFY_URL = getattr(
            dj, 'PAYFAST_NOTIFY_URL', cls.NOTIFY_URL
        )
        dj.PAYFAST_CACHE_TIMEOUT = getattr(
            dj, 'PAYFAST_CACHE_TIMEOUT', cls.CACHE_TIMEOUT
        )
        dj.PAYFAST_CACHE_KEY_PREFIX = getattr(
            dj, 'PAYFAST_CACHE_KEY_PREFIX', cls.CACHE_KEY_PREFIX
        )
        dj.PAYFAST_GRACE_PERIOD_DAYS = getattr(
            dj, 'PAYFAST_GRACE_PERIOD_DAYS', cls.GRACE_PERIOD_DAYS
        )




settings = Settings
