import requests
from requests.auth import HTTPBasicAuth
from .blesta_response import BlestaResponse

class BlestaApi:
    """
    Blesta API processor
    """

    def __init__(self, url, user, key):
        """
        Initializes the API

        :param url: The URL to the Blesta API
        :param user: The API user
        :param key: The API key
        """
        self.url = url.rstrip('/') + '/'
        self.user = user
        self.key = key
        self._last_request = None

    def get(self, model, method, args=None):
        return self.submit(model, method, args, "GET")

    def post(self, model, method, args=None):
        return self.submit(model, method, args, "POST")

    def put(self, model, method, args=None):
        return self.submit(model, method, args, "PUT")

    def delete(self, model, method, args=None):
        return self.submit(model, method, args, "DELETE")

    def submit(self, model, method, args=None, action="POST"):
        if args is None:
            args = {}

        url = f"{self.url}{model}/{method}.json"
        self._last_request = {'url': url, 'args': args}

        try:
            if action == "GET":
                response = requests.get(url, params=args, auth=HTTPBasicAuth(self.user, self.key))
            elif action == "POST":
                response = requests.post(url, data=args, auth=HTTPBasicAuth(self.user, self.key))
            elif action == "PUT":
                response = requests.put(url, data=args, auth=HTTPBasicAuth(self.user, self.key))
            elif action == "DELETE":
                response = requests.delete(url, data=args, auth=HTTPBasicAuth(self.user, self.key))
            else:
                raise ValueError("Invalid HTTP action specified.")

            return BlestaResponse(response.text, response.status_code)
        
        except requests.RequestException as e:
            return BlestaResponse(str(e), 500)

    def get_last_request(self):
        """
        Returns the details of the last request made.

        :return: Dictionary with URL and args of the last request.
        """
        return self._last_request