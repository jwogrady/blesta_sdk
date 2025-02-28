import requests
from requests.auth import HTTPBasicAuth
from blesta_sdk.core import BlestaResponse
from urllib.parse import urljoin
import logging

logging.basicConfig(level=logging.ERROR)


class BlestaRequest:
    """
    Blesta API processor for making HTTP requests to the Blesta API.
    """

    def __init__(self, url, user, key):
        """
        Initializes the BlestaRequest instance.

        :param url: The base URL of the Blesta API.
        :param user: The API user.
        :param key: The API key.
        """
        self.base_url = url.rstrip("/") + "/"
        self.user = user
        self.key = key
        self._last_request = None
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.user, self.key)

    def get(self, model, method, args=None):
        """
        Makes a GET request to the Blesta API.

        :param model: The API model (e.g., 'clients').
        :param method: The API method (e.g., 'getList').
        :param args: Optional dictionary of query parameters.
        :return: BlestaResponse object containing the response data.
        """
        return self.submit(model, method, args, "GET")

    def post(self, model, method, args=None):
        """
        Makes a POST request to the Blesta API.

        :param model: The API model (e.g., 'clients').
        :param method: The API method (e.g., 'create').
        :param args: Optional dictionary of data to send in the body of the request.
        :return: BlestaResponse object containing the response data.
        """
        return self.submit(model, method, args, "POST")

    def put(self, model, method, args=None):
        """
        Makes a PUT request to the Blesta API.

        :param model: The API model (e.g., 'clients').
        :param method: The API method (e.g., 'update').
        :param args: Optional dictionary of data to send in the body of the request.
        :return: BlestaResponse object containing the response data.
        """
        return self.submit(model, method, args, "PUT")

    def delete(self, model, method, args=None):
        """
        Makes a DELETE request to the Blesta API.

        :param model: The API model (e.g., 'clients').
        :param method: The API method (e.g., 'delete').
        :param args: Optional dictionary of data to send in the body of the request.
        :return: BlestaResponse object containing the response data.
        """
        return self.submit(model, method, args, "DELETE")

    def submit(self, model, method, args=None, action="POST"):
        """
        Submits an HTTP request to the Blesta API.

        :param model: The API model (e.g., 'clients').
        :param method: The API method (e.g., 'getList').
        :param args: Optional dictionary of data or query parameters.
        :param action: The HTTP action to perform ('GET', 'POST', 'PUT', 'DELETE').
        :return: BlestaResponse object containing the response data.
        """
        if args is None:
            args = {}

        url = urljoin(self.base_url, f"{model}/{method}.json")
        self._last_request = {"url": url, "args": args}

        try:
            if action == "GET":
                response = self.session.get(url, params=args)
            elif action == "POST":
                response = self.session.post(url, json=args)
            elif action == "PUT":
                response = self.session.put(url, json=args)
            elif action == "DELETE":
                response = self.session.delete(url, json=args)
            else:
                raise ValueError("Invalid HTTP action specified.")

            response.raise_for_status()
            return BlestaResponse(response.text, response.status_code)

        except requests.RequestException as e:
            logging.error(f"Request failed: {e}")
            return BlestaResponse(str(e), 500)

    def get_last_request(self):
        """
        Returns the details of the last request made.

        :return: Dictionary with URL and args of the last request.
        """
        return self._last_request
