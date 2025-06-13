import json
import logging
from typing import Optional, Any, Dict

import requests
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from . import user_utils
from ..models import Client, UserSettings, get_user_by_id

logger = logging.getLogger(__name__)


# Utility function to create a client in the database
def create_client(parameters) -> tuple[str, int] | tuple[Client, int]:
    """
    Creates a client in the database.

    Args:
        parameters (dict): Parameters for the client.
        {
            "user_id": int,
            "name": str,
            "local_ip": str,
            "port": int,
            "allowed_users": list[int],
        }
    Returns:
        tuple: A tuple containing either the Client object and status code (200) or an error message and status code (400).
    """
    # Check the parameters dictionary for the required keys
    expected_types = {
        "user_id": int,
        "name": str,
        "local_ip": str,
        "port": int,
        "allowed_users": list[int]
    }
    # Check if the dictionary contains the expected keys and types
    for key, expected_type in expected_types.items():
        if key not in parameters:
            return f"Missing parameter: {key}", 400
        if not isinstance(parameters[key], expected_type):
            return f"Invalid type for parameter {key}: expected {expected_type}, got {type(parameters[key])}", 400

    # Check if the user exists in the database
    user_id = parameters["user_id"]
    existing_user, code = user_utils.get_user_by_id(user_id)
    if code != 200:
        return existing_user, code  # Raise the error message and status code if user not found

    # Create the client
    client, created = Client.objects.get_or_create(
        user=existing_user,
        name=parameters["name"],
        local_ip=parameters["local_ip"],
        port=parameters["port"],
        allowed_users=parameters["allowed_users"],
    )

    return client, 200  # OK


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
    user, code = get_user_by_id(user_id)
    if code != 200:
        logger.error(f"User with ID {user_id} not found.")
        return user, code  # Return an empty list if the user is not found
    # Filter the clients based on if the user_id is on the allowed_users list
    clients = [client for client in clients if client.is_user_allowed(user_id)]

    return clients, 200  # Return the list of clients


# Utility function to get a client by ID
def get_client_by_id(client_id: int) -> tuple[str | Client, int]:
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


def send_client_post_request(**kwargs: Dict[str, Any]) -> tuple[dict | str, int]:
    """
    Sends a POST request to a specific API endpoint on a client application
    with a JSON body and custom headers. It also checks if the user is allowed to access the client (if the client's API key is on it's UserSettings).

    Args:
        kwargs (dict):
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
    # Check if the kwargs are of the expected types
    for param, expected_type in expected_types.items():
        if param not in kwargs or not isinstance(kwargs[param], expected_type):
            logger.error(f"send_client_post_request() - Invalid parameter '{param}' or type mismatch.")
            return f"send_client_post_request() - Invalid parameter '{param}' or type mismatch.", 400

    client_id: int = kwargs.get('client_id')  # Get the client ID from kwargs
    user_id: int = kwargs.get('user_id')  # Get the user ID from kwargs
    endpoint: str = kwargs.get('endpoint')  # Get the endpoint from kwargs
    body = kwargs.get('body', {})  # Use an empty dict if body is not provided
    headers = kwargs.get('headers', {})  # Use an empty dict if headers are not provided

    # --- Check User Allowance for the Client ---
    # Fetch the client object from the database using the provided client_id
    client_obj, code = get_client_by_id(client_id)
    if code != 200:
        logger.error(f"send_client_post_request() - Error retrieving Client with ID {client_id} not found.")
        return client_obj, code
    client_obj: Client

    # Fetch the user object from the database using the provided user_id
    user_obj, code = get_user_by_id(user_id)
    if code != 200:
        logger.error(f"send_client_post_request() - Error retrieving User with ID {user_id} not found.")
        return user_obj, code
    user_obj: User

    # Use the is_user_allowed method of the Client model
    if not client_obj.is_user_allowed(user_id):
        logger.debug(
            f"api_update_program_list() - User '{user_obj.username}' is not allowed to access client {client_obj}.")
        return f"{user_obj} is not allowed to access {client_obj}.", 403  # Forbidden

    # Construct the full URL for the client application's API endpoint
    # Ensure endpoint doesn't have a leading slash if the base URL already ends with one
    base_url = f"http://{client_obj.local_ip}:{client_obj.port}"
    # Simple join: handles cases where endpoint might or might not have a leading slash
    client_api_url = f"{base_url}/{endpoint.lstrip('/')}"
    logger.debug(f"send_client_post_request() - Constructed client API URL: {client_api_url}")

    # Combine default headers (like Content-Type for JSON) with provided headers
    request_headers = {'Content-Type': 'application/json'}
    if headers:
        request_headers.update(headers)  # Add/override headers from the provided dictionary

    # --- Authentication for Server-to-Client Requests ---
    # When the server makes requests to the client, it needs to authenticate itself. It uses an API key stored in the user's settings.
    server_auth_key, code = user_utils.get_user_settings(user_obj).get_client_api_key(client_id)
    if code != 200:
        logger.warning(
            f"send_client_post_request() - Error retrieving server authentication key for client {client_obj}.")
        # Function continues, there are some client funtions that does not require a server authentication key

    request_headers['X-Server-API-Key'] = server_auth_key if server_auth_key else ''

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


def send_client_get_request(client: int | Client, endpoint: str, **kwargs: Optional[Any]) -> tuple[dict, int] | tuple[
    str, int]:
    """
    Sends a GET request to a specific API endpoint on a client application.

    Args:
        client (int | Cleint): The Django Client ID representing the client or the client object.
        endpoint (str): The API endpoint path on the client (e.g., 'api/status/', 'api/commands/').
                        Should NOT start with a leading slash if joining with base URL.
    Returns:
        dict: The parsed JSON response received from the client (a dict),
                              or None if the request fails or the response is invalid.
        code: The HTTP status code of the response, or an appropriate error code (e.g., 500, 400) on failure
    """
    if not client:
        logger.error("send_client_get_request() - Received None client.")
        return "send_client_get_request() - Received None client.", 400
    if not endpoint:
        logger.error("send_client_get_request() - Received empty endpoint string.")
        return "send_client_get_request() - Received empty endpoint string.", 400

    # Fetch the client object from the database using the provided client_id
    if isinstance(client, int):
        client_obj, code = get_client_by_id(client)
    elif isinstance(client, Client):
        client_obj = client
        code = 200  # Assume client is valid if it's already a Client object
    else:
        logger.error(f"send_client_get_request() - Invalid client type: {type(client)}. Expected int or Client object.")
        return "send_client_get_request() - Invalid client type. Expected int or Client object.", 400

    if code != 200:
        logger.error(f"send_client_post_request() - Client with ID {client} not found.")
        return f"Client with ID {client} not found.", 404  # Not Found

    # Construct the full URL for the client application's API endpoint
    base_url = f"http://{client_obj.local_ip}:{client_obj.port}"
    # Simple join that handles cases where endpoint might or not have a leading slash
    client_api_url = f"{base_url}/{endpoint.lstrip('/')}"
    if kwargs:
        first = True  # Flag to track if this is the first query parameter
        # If there are additional query parameters, append them to the URL
        query_string = '&'.join(f"{key}={value}" for key, value in kwargs.items() if value is not None)
        if query_string:
            client_api_url += '?' if first else '&' + query_string

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
        # Client not available/responsive - use a suitable status code
        return f"Request to client {client_obj} at {endpoint} timed out. Client API unreachable.", 504  # Gateway Timeout

    except requests.exceptions.ConnectionError as e:
        logger.error(f"send_client_get_request() - Could not connect to client {client_obj} at {endpoint}: {e}")
        # Client not available/unreachable - use a suitable status code
        return f"Could not connect to client {client_obj} at {endpoint}. Client API unreachable.", 503  # Service Unavailable

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
