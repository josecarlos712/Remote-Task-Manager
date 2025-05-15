import requests
import json
import os
from django.conf import settings
import logging

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from ..models import Client, UserSettings
from ..utils.APIResponse import NotFoundResponse, InternalErrorResponse, UnauthorizedResponse

logger = logging.getLogger(__name__)


def get_absolute_path(relative_path: str) -> str:
    """
    Resolves a relative path within the Django project to an absolute path.

    Args:
        relative_path (str): The path relative to the project's BASE_DIR.

    Returns:
        str: The absolute path.

    Raises:
        TypeError: If the input relative_path is not a string.
    """
    if not isinstance(relative_path, str):
        logger.error(f"resolve_project_path() - Input path must be a string, received {type(relative_path)}")
        raise TypeError("Input path must be a string")

    # settings.BASE_DIR is the absolute path to your project's root directory
    # os.path.join safely joins path components, handling different OS path separators
    absolute_path = os.path.join(settings.BASE_DIR, relative_path.strip('/').replace('/', '\\'))

    logger.debug(f"Resolved relative path '{relative_path}' to absolute path '{absolute_path}'")

    return absolute_path


# This function reads all the configuration files and stores it on a dictionary to be readable.
def read_config():
    # Get the current script's directory
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Navigate to the config folder and construct the full path to paths.json
    config_path = os.path.join(current_dir, '../config', 'paths.json')

    try:
        with open(config_path, 'r') as config_file:
            config_data = json.load(config_file)
            print(config_data)
        return config_data
    except FileNotFoundError:
        return f"Configuration file not found: {config_path}"
    except json.JSONDecodeError:
        return "Error decoding JSON from the configuration file: {config_path}"


def verify_and_create_directory(directory_path: str, logger=None) -> tuple[bool, str]:
    """
    Verifies if a given path is an absolute directory and creates it if it doesn't exist.

    Args:
        directory_path (str): The full path to the directory to check/create.
        logger (logging.Logger, optional): A logger instance to use for logging messages.
                                           If None, a basic logger will be used or messages
                                           will be printed (depending on logger configuration).

    Returns:
        tuple[bool, str]: A tuple containing:
                          - bool: True if the directory exists or was successfully created, False otherwise.
                          - str: A message indicating the outcome (success or error details).
    """
    # Use the provided logger or a default one if none is provided
    log = logger if logger else logging.getLogger(__name__)

    # Check if the path is absolute
    if not os.path.isabs(directory_path):
        log.error(f"verify_and_create_directory ERROR: Path '{directory_path}' is not an absolute path.")
        return False, f"Error: Path '{directory_path}' is not an absolute path."

    # Check if the path exists and is a directory
    if os.path.exists(directory_path):
        if os.path.isdir(directory_path):
            log.debug(f"verify_and_create_directory: Directory already exists at '{directory_path}'.")
            return True, f"Directory already exists at '{directory_path}'."
        else:
            # Path exists but is not a directory (e.g., a file)
            log.error(f"verify_and_create_directory ERROR: Path '{directory_path}' exists but is not a directory.")
            return False, f"Error: Path '{directory_path}' exists but is not a directory."
    else:
        # Directory does not exist, attempt to create it
        try:
            os.makedirs(directory_path, exist_ok=True)
            log.debug(f"verify_and_create_directory: Created directory at '{directory_path}'.")
            return True, f"Created directory at '{directory_path}'."
        except Exception as e:
            log.error(f"verify_and_create_directory ERROR: Exception creating directory '{directory_path}' - {e}")
            return False, f"Error creating directory '{directory_path}': {e}"


def send_client_post_request(client_id: int, user: User, endpoint: str, body: dict = None, headers: dict = None) -> tuple:
    """
    Sends a POST request to a specific API endpoint on a client application
    with a JSON body and custom headers.

    Args:
        client_id (int): The Django Client ID from the DB.
        user (User): The Django User object making the request.
        endpoint (str): The API endpoint path on the client (e.g., 'api/commands/execute/').
        body (dict, optional): The dictionary to send as the JSON request body. Defaults to None.
        headers (dict, optional): A dictionary of custom headers to include in the request. Defaults to None.

    Returns:
        tuple: A tuple containing:
               - dict or error message: The parsed JSON response received from the client (can be a dict or list),
                                      or None if the request fails or the response is invalid.
               - int: The HTTP status code of the response, or an appropriate error code (e.g., 500, 400) on failure
                      if no response status is available.
    """
    if not client_id:
        logger.error("send_client_post_request() - Received None clien_id.")
        return "send_client_post_request() - Received None clien_id.", 400  # Bad Request due to invalid input

    if not endpoint:
        logger.error("send_client_post_request() - Received empty endpoint string.")
        return "send_client_post_request() - Received empty endpoint string.", 400  # Bad Request due to invalid input

    if body is not None and not isinstance(body, dict):
        logger.error(
            f"send_client_post_request() - Received invalid body format. Expected dict or None, got {type(body)}.")
        return f"send_client_post_request() - Received invalid body format. Expected dict or None, got {type(body)}.", 400  # Bad Request due to invalid input

    if headers is not None and not isinstance(headers, dict):
        logger.error(
            f"send_client_post_request() - Received invalid headers format. Expected dict or None, got {type(headers)}.")
        return f"send_client_post_request() - Received invalid headers format. Expected dict or None, got {type(headers)}.", 400  # Bad Request due to invalid input

    # --- Check User Allowance for the Client ---
    # Fetch the client object from the database using the provided client_id
    client_obj, success = Client.get_client_by_ID(client_id)
    if not success:
        logger.error(f"send_client_post_request() - Client with ID {client_id} not found.")
        return f"Client with ID {client_id} not found.", 404  # Not Found
    # Use the is_user_allowed method of the Client model
    if not client_obj.is_user_allowed(user):
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


def send_client_get_request(client_id: int, endpoint: str) -> tuple:
    """
    Sends a GET request to a specific API endpoint on a client application.

    Args:
        client_id (int): The Django Client ID representing the client.
        endpoint (str): The API endpoint path on the client (e.g., 'api/status/', 'api/commands/').
                        Should NOT start with a leading slash if joining with base URL.

    Returns:
        dict or list or None: The parsed JSON response received from the client (can be a dict or list),
                              or None if the request fails or the response is invalid.
    """
    if not client_id:
        logger.error("send_client_get_request() - Received None client ID.")
        return None, 400
    if not endpoint:
        logger.error("send_client_get_request() - Received empty endpoint string.")
        return None, 400

    # Fetch the client object from the database using the provided client_id
    client_obj, success = Client.get_client_by_ID(client_id)
    if not success:
        logger.error(f"send_client_post_request() - Client with ID {client_id} not found.")
        return f"Client with ID {client_id} not found.", 404  # Not Found

    # Construct the full URL for the client application's API endpoint
    base_url = f"http://{client_obj.local_ip}:{client_obj.port}"
    # Simple join that handles cases where endpoint might or not have a leading slash
    client_api_url = f"{base_url}/{endpoint.lstrip('/')}"

    # TODO: Implement API key management for client requests. Add API key to headers..

    logger.debug(f"send_client_get_request() - Sending GET request to {client_api_url} for client {client_obj}")

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
        return None, response.status_code  # Indicate failure

    except requests.exceptions.ConnectionError:
        logger.error(f"send_client_get_request() - Could not connect to client {client_obj} at {endpoint}.")
        return None, response.status_code  # Indicate failure

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
        return None, response.status_code  # Indicate failure

    except json.JSONDecodeError:
        logger.error(f"send_client_get_request() - Invalid JSON response from client {client_obj} at {endpoint}.",
                     exc_info=True)
        return None, response.status_code  # Indicate failure

    except Exception as e:
        # Catch any other unexpected errors
        logger.error(
            f"send_client_get_request() - An unexpected error occurred for client {client_obj} at {endpoint}: {e}",
            exc_info=True)
        return None, response.status_code  # Indicate failure


def check_None(value, error_message: str = None, skip: bool = False):
    """
    Check if the given value is None or empty.

    Args:
        value: The value to check.
        error_message (str, optional): An error message to log if the value is None or empty.
        skip (bool, optional): If True, returns False anyway, just logs.
    Returns:
        tuple: A tuple containing True/False (is None, is not None) and an HTTP status code.
    """
    if value is None:
        logger.error(error_message)
        if not skip:
            return True, 400
    return False, 200


def check_instance(obj, instance, error_message: str = None, skip: bool = False):
    """
    Check if the given object is an instance of a specific class.
    Args:
        obj: The object to check.
        instance: The class or type to check against.
        error_message (str, optional): An error message to log if the object is not an instance of the class.
        skip (bool, optional): If True, returns False anyway, just logs.
    Returns:
       tuple: A tuple containing True/False (is None, is not None) and an HTTP status code.
    """
    if obj is isinstance(obj, instance):
        logger.error(error_message)
        if not skip:
            return True, 400
    return False, 200
