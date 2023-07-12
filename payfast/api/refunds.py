from payfast.base import Resource




class Refund:

    def __init__(self, data):
        pass




class Refunds(Resource):

    key = 'refunds'


    def query(self):
        """
        GET /refunds/query/:id

        Step 1.
        """
        raise NotImplementedError


    def create(self):
        """
        POST /refunds/:id

        Step 2.
        Create a new refund.
        """
        raise NotImplementedError


    def get(self):
        """
        GET /refunds/:id
        """
        raise NotImplementedError
