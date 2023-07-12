

class PayFastException(Exception):
    pass




class PayFastTimeout(Exception):
    pass




class PayFastMinAmountException(PayFastException):

    def __init__(self, amount):
        from payfast import constants
        amount = str(amount)
        min_amount = constants.PAYFAST_MIN_AMOUNT
        message = (
            f'The amount provided "{amount}" cannot be smaller than {min_amount}.'
        )




# Copied and modified from: https://github.com/SparkPost/python-sparkpost/blob/master/sparkpost/exceptions.py
class PayFastAPIException(PayFastException):

    def __init__(self, response, *args, **kwargs):
        """
        :param response: The ``PayFastResponse`` object related to the exception.
        """
        # noinspection PyBroadException
        # try:
        #     errors = response.json()['errors']
        #     error_template = "{message} Code: {code} Description: {desc} \n"
        #     errors = [error_template.format(message=e.get('message', ''),
        #                                     code=e.get('code', 'none'),
        #                                     desc=e.get('description', 'none'))
        #               for e in errors]
        # # TODO: select exception to catch here
        # except:  # noqa: E722
        #     errors = [response.text or ""]
        from payfast.base import PayFastResponse

        # Do this check just in case.
        if isinstance(response, PayFastResponse):
            response = response.orig

        errors = [response.text or ""]
        self.status = response.status_code
        self.response = response
        self.errors = errors
        message = """Call to {uri} returned {status_code}, errors:

        {errors}

        """.format(
            uri=response.url,
            status_code=response.status_code,
            errors='\n'.join(errors)
        )
        super().__init__(message, *args, **kwargs)
