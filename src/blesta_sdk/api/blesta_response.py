import json


class BlestaResponse:
    """
    Blesta API response handler
    """

    def __init__(self, response, response_code):
        """
        Initializes the Blesta Response

        :param response: The raw response data from an API request
        :param response_code: The HTTP response code for the request
        """
        self._raw = response
        self._response_code = response_code

    @property
    def response(self):
        """
        Returns the parsed 'response' data from the API request.

        :return: A dictionary if 'response' exists, else None
        """
        formatted = self._format_response()
        return formatted.get("response")

    @property
    def response_code(self):
        """
        Returns the HTTP response code.

        :return: The HTTP response code for the request
        """
        return self._response_code

    @property
    def raw(self):
        """
        Returns the raw API response.

        :return: The raw response as a string
        """
        return self._raw

    def errors(self):
        """
        Returns any errors present in the response.

        :return: Dictionary of errors or False if no errors
        """
        if self._response_code != 200:
            formatted = self._format_response()
            return formatted.get("errors", {"error": formatted})
        return False

    def _format_response(self):
        """
        Parses the raw response into a dictionary.

        :return: Parsed JSON response
        """
        try:
            return json.loads(self._raw)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response"}
