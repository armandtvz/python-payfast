import json
import logging
from datetime import datetime
from urllib.parse import urljoin
import urllib.parse

import requests

from payfast import timezone
from payfast.conf import settings
from payfast.signature import make_signature
from payfast.exceptions import PayFastAPIException, PayFastTimeout

logger = logging.getLogger('payfast')




class PayFastResponse:

    def __init__(self, response):
        """
        Example responses received from PayFast can be found in
        ``payfast/responses.txt``.

        :param response: The response as received from ``python-requests``.
        """
        self.orig = response
        self.status_code = response.status_code
        self.ok = response.ok

        # These are the things that we will find in a variety
        # of API responses from PayFast. Some values might be
        # empty/unused depending on the type of response.
        self.code: int = 0
        self.status: str = ''
        self.data: dict = {}
        # The response attribute, as received from PayFast's API, is not
        # of a single type. The response value can be any of the following:
        # - int
        # - str
        # - bool
        # - dict
        # The response value is the envelope.
        self.response = None
        self.message: str = ''
        self.text = ''

        self.json = {}
        self.http_status = response.status_code
        try:
            self.json = response.json()
        except requests.JSONDecodeError:
            self.text = response.content.decode()
        logger.debug(json.dumps(self.json, indent=4))

        if isinstance(self.json, dict):
            self.code = self.json.get('code', 0)
            self.status = self.json.get('status', '')
            self.data = self.json.get('data', {})

            self.response = self.data.get('response', None)
            self.message = self.data.get('message', '')
            if not self.response:
                # The transactions API doesn't nest the response value.
                self.response = self.json.get('response', None)

        elif isinstance(self.json, str):
            if not self.text:
                self.text = self.json

        try:
            self.code = int(self.code)
        except (ValueError, TypeError):
            self.code = self.status_code
        try:
            if self.response.lower() == 'not found':
                # As far as I can remember PayFast returns a 400 status
                # on some requests instead of a 404.
                if self.code != 404:
                    self.code = 404
        except AttributeError:
            pass

        if not self.code:
            self.code = self.status_code

        self.payload = self.response
        if self.ok:
            if not (200 <= self.code < 300):
                self.ok = False




class RequestsTransport:

    def __init__(self, api_version):
        self.api_version = api_version
        self.session = requests.Session()


    def handle_response(self, response, raise_for_status=True) -> PayFastResponse:
        response = PayFastResponse(response)
        if raise_for_status:
            if not response.ok or not response.code:
                raise PayFastAPIException(response)
        return response


    def request(
        self,
        method,
        uri,
        payload=None,
        params=None,
        headers=None,
        raise_for_status=True,
        urlencode=False,
        **kwargs
    ):
        if not headers:
            for_headers = payload or params
            content_type = None
            if method.lower() != 'get':
                content_type = 'application/json'
                if urlencode:
                    content_type = 'application/x-www-form-urlencoded'
            headers = self.get_headers(for_headers, content_type=content_type)

        if settings.DEBUG:
            # NOTE: Do not use ``uri += '/?testing=true'`` (no forward slash)
            # as that will result in a redirect which will cause the request
            # to fail with a 405 Method Not Allowed status.
            uri += '?testing=true'

        request_args = {
            'method': method,
            'url': uri,
            'headers': headers,
        }
        if payload:
            if urlencode:
                payload = urllib.parse.urlencode(payload)
            else:
                payload = json.dumps(payload)
            request_args['data'] = payload

        elif params:
            request_args['params'] = params

        logger.debug(json.dumps(request_args, indent=4))

        req = requests.Request(**request_args)
        req = req.prepare()
        response = None
        try:
            response = self.session.send(
                req,
                timeout=settings.API_TIMEOUT,
                allow_redirects=False,
            )
        except (
            requests.ConnectionError,
            requests.Timeout
        ):
            raise PayFastTimeout()

        response = self.handle_response(
            response,
            raise_for_status=raise_for_status,
        )
        return response


    def get_headers(self, payload, content_type=None):
        # There's a bug on PayFast's API where they don't account
        # for microseconds which means that using datetime.isoformat()
        # will not work.
        # timestamp = timezone.now().isoformat()
        timestamp = timezone.now()
        timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S')
        headers = {
            'merchant-id': str(settings.MERCHANT_ID),
            'version': self.api_version,
            'timestamp': str(timestamp),
        }
        for_signature = headers
        if payload:
            if isinstance(payload, dict):
                for_signature = {
                    **headers,
                    **payload,
                }
            elif isinstance(payload, str):
                for_signature['payload'] = payload
        signature = make_signature(for_signature, a12y=True)
        headers['signature'] = signature

        if content_type:
            headers['content-type'] = content_type
        return headers




class Resource:

    key = None


    def __init__(self, api_version, transport_class=RequestsTransport):
        self.base_uri = settings.API_ROOT
        self.transport = transport_class(api_version)


    def request(self, method, uri, **kwargs):
        response = self.transport.request(
            method,
            uri,
            **kwargs,
        )
        return response


    @property
    def uri(self):
        return urljoin(self.base_uri, self.key)


    def get(self):
        raise NotImplementedError


    def fetch(self):
        raise NotImplementedError


    def list(self):
        raise NotImplementedError


    def create(self):
        raise NotImplementedError


    def update(self):
        raise NotImplementedError


    def delete(self):
        raise NotImplementedError


    def cancel(self):
        raise NotImplementedError
