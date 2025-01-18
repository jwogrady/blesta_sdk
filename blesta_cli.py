import argparse
import os
from dotenv import load_dotenv
from api.blesta_api import BlestaApi
import json

# Load environment variables from .env file
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Blesta API Command Line Interface")
    parser.add_argument('--model', required=True, help='Blesta API model (e.g., clients)')
    parser.add_argument('--method', required=True, help='Blesta API method (e.g., getList)')
    parser.add_argument('--action', choices=['GET', 'POST', 'PUT', 'DELETE'], default='GET', help='HTTP action')
    parser.add_argument('--params', nargs='*', help='Optional key=value pairs (e.g., id=1 status=active)')

    args = parser.parse_args()

    # Load credentials from .env
    url = os.getenv("BLESTA_API_URL")
    user = os.getenv("BLESTA_API_USER")
    key = os.getenv("BLESTA_API_KEY")

    if not all([url, user, key]):
        print("Error: Missing API credentials in .env file.")
        return

    # Parse key=value arguments into a dictionary
    params = dict(param.split('=') for param in args.params) if args.params else {}

    # Initialize the API
    api = BlestaApi(url, user, key)

    # Perform the API action
    response = api.submit(args.model, args.method, params, args.action)

    # Print the response
    if response.response_code == 200:
        print("Success:", json.dumps(response.response, indent=4))
    else:
        print("Error:", response.errors)

if __name__ == "__main__":
    main()