import json
import logging

import requests
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from . import user_utils
from ..models import Client

logger = logging.getLogger(__name__)


# Utility function to get all clients associated with a user
def get_clients_by_user(user_id: int) -> tuple[list[Client], int] | tuple[str, int]:
    """
    Retrieves a list of clients associated with a specific user.

    Args:
        user_id (int): The ID of the user whose clients are to be retrieved.

    Returns:
        list: A list of Client objects associated with the user.
    """
    # Get all the clients from the database
    clients = Client.objects.all()
    print(clients)
    # Get user object by user_id
    user, code = user_utils.get_user_by_id(user_id)
    if code != 200:
        logger.error(f"User with ID {user_id} not found.")
        return user, code  # Return an empty list if the user is not found
    # Filter the clients based on if the user_id is on the allowed_users list
    clients = [client for client in clients if client.is_user_allowed(user_id)]

    return clients, 200  # Return the list of clients


# Utility function to get a client by ID
def get_client_by_id(client_id) -> tuple[str | Client, int]:
    """
    Retrieves a client instance by its ID.

    Args:
        client_id (int): The Client ID representing the client sending the program list.

    Returns:
        tuple (String/Client, int): Returns a tuple containing the client object or a error message and a boolean indicating success.
    """
    try:
        client_obj = Client.objects.get(pk=client_id)
        logger.debug(f"api_update_program_list() - Successfully retrieved client: {client_obj}")
        return client_obj, 200

    except ObjectDoesNotExist:
        logger.warning(f"api_update_program_list() - Client with ID '{client_id}' not found.")
        return f"api_update_program_list() - Client with ID '{client_id}' not found.", 404

    except MultipleObjectsReturned:
        logger.error(f"api_update_program_list() - Multiple clients found for ID '{client_id}'. Database error?")
        return f"api_update_program_list() - Multiple clients found for ID '{client_id}'. Database error?", 500

    except Exception as e:
        logger.error(f"api_update_program_list() - Error retrieving client '{client_id}': {e}", exc_info=True)
        return f"api_update_program_list() - Error retrieving client '{client_id}': {e}", 500


# Utility function to get a client base endpoint
def get_client_base_endpoint(client_id: int) -> tuple[str, int]:
    """
    Retrieves the base endpoint for a specific client.

    Args:
        client_id (int): The ID of the client whose base endpoint is to be retrieved.

    Returns:
        str: The base endpoint URL for the client.
    """
    client, code = get_client_by_id(client_id)
    if code != 200:
        return client, code  # Return an error message if the client is not found

    # Build the base endpoint URL
    base_endpoint = f"http://{client.local_ip}:{client.port}/"

    return base_endpoint, 200  # Return the base endpoint URL


def send_client_post_request(parameters: dict) -> tuple[dict | str, int]:
    """
    Sends a POST request to a specific API endpoint on a client application
    with a JSON body and custom headers. It also checks if the user is allowed to access the client (if the client's API key is on it's UserSettings).

    Args:
        parameters (dict):
            - client_id (int): The Django Client ID representing the client.
            - user_id (int): The user object representing the user making the request.
            - endpoint (str): The API endpoint path on the client (e.g., 'api/status/', 'api/commands/').
            - body (dict): The JSON body to be sent in the POST request.
            - headers (dict): Optional custom headers to include in the request.

    Returns:
        tuple: A tuple containing:
               - dict or error message: The parsed JSON response received from the client (can be a dict or list),
                                      or None if the request fails or the response is invalid.
               - int: The HTTP status code of the response, or an appropriate error code (e.g., 500, 400) on failure
                      if no response status is available.
    """
    # Check parameters
    expected_types = {
        "client_id": int,
        "user_id": int,
        "endpoint": str,
        "body": dict,
        "headers": dict,
    }
    # Check if the parameters are of the expected types
    for param, expected_type in expected_types.items():
        if param not in parameters or not isinstance(parameters[param], expected_type):
            logger.error(f"send_client_post_request() - Invalid parameter '{param}' or type mismatch.")
            return f"send_client_post_request() - Invalid parameter '{param}' or type mismatch.", 400

    # --- Check User Allowance for the Client ---
    # Fetch the client object from the database using the provided client_id
    client_obj, code = get_client_by_id(parameters['client_id'])
    if code != 200:
        logger.error(f"send_client_post_request() - Error retrieving Client with ID {parameters['client_id']} not found.")
        return client_obj, code

    # Fetch the user object from the database using the provided user_id
    user, code = user_utils.get_user_by_id(parameters['user_id'])
    if code != 200:
        logger.error(f"send_client_post_request() - Error retrieving User with ID {parameters['user_id']} not found.")
        return user, code

    # Use the is_user_allowed method of the Client model
    if not client_obj.is_user_allowed(parameters['user_id']):
        logger.debug(
            f"api_update_program_list() - User '{user.username}' is not allowed to access client {client_obj}.")
        return f"{user} is not allowed to access {client_obj}.", 403  # Forbidden

    # Construct the full URL for the client application's API endpoint
    # Ensure endpoint doesn't have a leading slash if the base URL already ends with one
    base_url = f"http://{client_obj.local_ip}:{client_obj.port}"
    # Simple join: handles cases where endpoint might or might not have a leading slash
    client_api_url = f"{base_url}/{endpoint.lstrip('/')}"

    # Combine default headers (like Content-Type for JSON) with provided headers
    request_headers = {'Content-Type': 'application/json'}
    if headers:
        request_headers.update(headers)  # Add/override headers from the provided dictionary

    # --- Authentication for Server-to-Client Requests ---
    # When the server makes requests to the client, it needs to authenticate itself. It uses an API key stored in the user's settings.
    server_auth_key = UserSettings.get_client_api_key(user)

    if server_auth_key:
        # Include the server's secret key in a custom header
        request_headers['X-Server-API-Key'] = server_auth_key  # Example custom header
    else:
        request_headers['X-Server-API-Key'] = ''  # Empty string if no key found
        logger.warning(
            f"send_client_post_request() - No server authentication key found for client {client_obj}. A blank key will be sent.")
        # Decide if you want to proceed without a key or return None/raise error

    logger.debug(
        f"send_client_post_request() - Sending POST request to {client_api_url} for client {client_obj} with body: {body}")

    response = None  # Initialize response to None for error handling

    try:
        # Make the POST request to the client application's API
        # Use the 'json' parameter to automatically set Content-Type and send the dictionary as JSON
        response = requests.post(client_api_url, json=body, headers=request_headers, timeout=10)  # Added a timeout

        # Check the HTTP status code of the response from the client
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        # Attempt to parse the JSON response from the client application
        # Assuming the client application's API endpoint returns JSON
        parsed_response = response.json()
        logger.debug(
            f"send_client_post_request() - Successfully received response from client {client_obj} at {endpoint}.")
        logger.debug(f"send_client_post_request() - Received data: {parsed_response}")

        return parsed_response, response.status_code  # Return the parsed JSON response and status code

    except requests.exceptions.Timeout:
        logger.error(f"send_client_post_request() - Request to client {client_obj} at {endpoint} timed out.")
        # Return a gateway timeout status if available, otherwise 500
        status_code = response.status_code if response is not None and response.status_code >= 400 else 504
        return f"send_client_post_request() - Request to client {client_obj} at {endpoint} timed out.", status_code  # Indicate failure and timeout status

    except requests.exceptions.ConnectionError:
        logger.error(f"send_client_post_request() - Could not connect to client {client_obj} at {endpoint}.")
        # Return service unavailable status if available, otherwise 500
        status_code = response.status_code if response is not None and response.status_code >= 400 else 503
        return f"send_client_post_request() - Could not connect to client {client_obj} at {endpoint}.", status_code  # Indicate failure and connection error status

    except requests.exceptions.RequestException as e:
        # Catch any other requests-related errors (e.g., HTTPError from raise_for_status)
        logger.error(f"send_client_post_request() - Error forwarding request to client {client_obj} at {endpoint}: {e}",
                     exc_info=True)
        # Attempt to get error details from the client response body if available
        error_details = None
        status_code = 500  # Default to internal server error

        if response is not None:
            status_code = response.status_code  # Use the actual response status code if available
            try:
                if response.text:
                    error_details = response.json()  # Try parsing as JSON
                else:
                    error_details = response.text  # Fallback to text
            except:
                pass  # Ignore parsing errors here

        logger.error(
            f"Client responded with status {status_code}. Details: {error_details}")
        return f"Client responded with status {status_code}. Details: {error_details}", status_code  # Indicate failure and the client's status code (or 500)

    except json.JSONDecodeError:
        logger.error(f"send_client_post_request() - Invalid JSON response from client {client_obj} at {endpoint}.",
                     exc_info=True)
        # Return the response status code if available, otherwise 500
        status_code = response.status_code if response is not None and response.status_code >= 400 else 500
        return f"send_client_post_request() - Invalid JSON response from client {client_obj} at {endpoint}.", status_code  # Indicate failure and JSON decode error status

    except Exception as e:
        # Catch any other unexpected errors
        logger.error(
            f"send_client_post_request() - An unexpected error occurred for client {client_obj} at {endpoint}: {e}",
            exc_info=True)
        # Return 500 for unexpected errors
        return f"send_client_post_request() - An unexpected error occurred for client {client_obj} at {endpoint}: {e}", 500  # Indicate failure and internal server error status


def send_client_get_request(client_id: int, endpoint: str) -> tuple[dict, int] | tuple[str, int]:
    """
    Sends a GET request to a specific API endpoint on a client application.

    Args:
        client_id (int): The Django Client ID representing the client.
        endpoint (str): The API endpoint path on the client (e.g., 'api/status/', 'api/commands/').
                        Should NOT start with a leading slash if joining with base URL.
    Returns:
        dict: The parsed JSON response received from the client (a dict),
                              or None if the request fails or the response is invalid.
        code: The HTTP status code of the response, or an appropriate error code (e.g., 500, 400) on failure
    """
    if not client_id:
        logger.error("send_client_get_request() - Received None client ID.")
        return "send_client_get_request() - Received None client ID.", 400
    if not endpoint:
        logger.error("send_client_get_request() - Received empty endpoint string.")
        return "send_client_get_request() - Received empty endpoint string.", 400

    # Fetch the client object from the database using the provided client_id
    client_obj, success = get_client_by_id(client_id)
    if not success:
        logger.error(f"send_client_post_request() - Client with ID {client_id} not found.")
        return f"Client with ID {client_id} not found.", 404  # Not Found

    # Construct the full URL for the client application's API endpoint
    base_url = f"http://{client_obj.local_ip}:{client_obj.port}"
    # Simple join that handles cases where endpoint might or not have a leading slash
    client_api_url = f"{base_url}/{endpoint.lstrip('/')}"

    logger.debug(f"send_client_get_request() - Sending GET request to {client_api_url} for client {client_obj}")

    response = None
    try:
        # Make the GET request to the client application's API
        # TODO: Implement proper error handling for the requests.get call (timeouts, connection errors)
        response = requests.get(client_api_url, headers={}, timeout=5)  # Added a timeout

        # Check the HTTP status code of the response from the client
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        # Attempt to parse the JSON response from the client application
        # Assuming the client application's API endpoint returns JSON
        parsed_response = response.json()
        logger.debug(
            f"send_client_get_request() - Successfully received response from client {client_obj} at {endpoint}.")
        logger.debug(f"send_client_get_request() - Received data: {parsed_response}")

        return parsed_response, response.status_code  # Return the parsed JSON response

    except requests.exceptions.Timeout:
        logger.error(f"send_client_get_request() - Request to client {client_obj} at {endpoint} timed out.")
        return f"send_client_get_request() - Request to client {client_obj} at {endpoint} timed out.", response.status_code  # Indicate failure

    except requests.exceptions.ConnectionError:
        logger.error(f"send_client_get_request() - Could not connect to client {client_obj} at {endpoint}.")
        return f"send_client_get_request() - Could not connect to client {client_obj} at {endpoint}.", response.status_code  # Indicate failure

    except requests.exceptions.RequestException as e:
        # Catch any other requests-related errors (e.g., HTTPError from raise_for_status)
        logger.error(f"send_client_get_request() - Error getting data from client {client_obj} at {endpoint}: {e}",
                     exc_info=True)
        # Attempt to get error details from the client response body if available
        error_details = None
        try:
            if response and response.text:
                error_details = response.json()  # Try parsing as JSON
            else:
                error_details = response.text  # Fallback to text
        except:
            pass  # Ignore parsing errors here

        logger.error(
            f"Client responded with status {response.status_code if response else 'N/A'}. Details: {error_details}")
        return f"Client responded with status {response.status_code if response else 'N/A'}. Details: {error_details}", response.status_code  # Indicate failure

    except json.JSONDecodeError:
        logger.error(f"send_client_get_request() - Invalid JSON response from client {client_obj} at {endpoint}.",
                     exc_info=True)
        return f"send_client_get_request() - Invalid JSON response from client {client_obj} at {endpoint}.", response.status_code  # Indicate failure

    except Exception as e:
        # Catch any other unexpected errors
        logger.error(
            f"send_client_get_request() - An unexpected error occurred for client {client_obj} at {endpoint}: {e}",
            exc_info=True)
        return f"send_client_get_request() - An unexpected error occurred for client {client_obj} at {endpoint}: {e}", response.status_code  # Indicate failure
