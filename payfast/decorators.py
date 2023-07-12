import time
import json
import hashlib
import logging
from functools import wraps

try:
    from django.apps import apps
    from django.core.cache import cache
except ImportError:
    apps = None
    cache = None

from payfast.conf import settings

logger = logging.getLogger('payfast')




def cached(function):
    @wraps(function)
    def decorator(self, token, *args, **kwargs):
        from payfast.utils import make_key
        from payfast.api.subscriptions import Subscription

        fresh = kwargs.get('fresh', False)
        cache_only = kwargs.get('cache_only', False)
        nocache = not kwargs.get('cache', False)
        timeout = settings.CACHE_TIMEOUT
        if not cache:
            # If Django is not installed
            if cache_only:
                # TODO REVIEW:
                # Cache only is not relevant if Django is not installed.
                # Potentially raise an error.
                #
                # Or, mention that the cache=True will be ignored
                # if it can't be cached.
                pass
            return function(self, token, *args, **kwargs)
        else:
            if not apps.ready:
                return function(self, token, *args, **kwargs)

        key = make_key(token)
        if nocache:
            return function(self, token, *args, **kwargs)

        if fresh:
            cache.delete(key)

        cached_resp = cache.get(key)
        if cached_resp:
            try:
                cached_resp = json.loads(cached_resp)
            except json.JSONDecodeError as exc:
                raise
            token = cached_resp.get('token', None)
            logger.debug(f'Cache hit for PayFast subscription "{token}".')
            return Subscription(cached_resp)

        if cache_only:
            # We couldn't find anything in the cache so return
            return

        subscription_obj = function(self, token, *args, **kwargs)
        resp = json.dumps(subscription_obj.data)
        cache.set(key, resp, timeout=timeout)
        token = subscription_obj.token
        logger.debug(f'Cache miss for PayFast subscription "{token}".')
        return subscription_obj
    return decorator
