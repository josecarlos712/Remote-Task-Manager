import requests
import json
import os
from django.conf import settings
import logging

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.utils import timezone

from ..models import Client, UserSettings
from ..utils.APIResponse import NotFoundResponse, InternalErrorResponse, UnauthorizedResponse

logger = logging.getLogger(__name__)


# Format date to a relative time string
def time_ago(date):
    # Calculate the time difference
    now = timezone.now()  # Get the current timezone-aware time
    time_difference = now - date

    # Format the time difference into a human-readable string
    days = time_difference.days
    seconds = time_difference.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    time_ago_str_parts = []

    if days > 0:
        time_ago_str_parts.append(f"{days} {'día' if days == 1 else 'días'}")
    if hours > 0:
        time_ago_str_parts.append(f"{hours} {'hora' if hours == 1 else 'horas'}")
    if minutes > 0:
        time_ago_str_parts.append(f"{minutes} {'minuto' if minutes == 1 else 'minutos'}")
    if seconds > 0 and not time_ago_str_parts:  # Only show seconds if no larger unit is shown
        time_ago_str_parts.append(f"{seconds} {'segundo' if seconds == 1 else 'segundos'}")

    # Join the parts, or show "just now" if the difference is very small
    if time_ago_str_parts:
        # Join with "and" before the last part if there's more than one part
        if len(time_ago_str_parts) > 1:
            time_ago_str = ", ".join(time_ago_str_parts[:-1]) + " y " + time_ago_str_parts[-1]
        else:
            time_ago_str = time_ago_str_parts[0]
        time_ago_display = f"hace {time_ago_str}"
    else:
        time_ago_display = "justo ahora"  # For very recent activities
    return time_ago_display


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

    #logger.debug(f"Resolved relative path '{relative_path}' to absolute path '{absolute_path}'")

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


def check_None(value, error_message: str = None, skip: bool = False) -> tuple[bool, int] | tuple[str, int]:
    """
    Check if the given value is None or empty.

    Args:
        value: The value to check.
        error_message (str, optional): An error message to log if the value is None or empty.
        skip (bool, optional): If True, returns False anyway, just logs.
    Returns:
        tuple: A tuple containing True/error_message (is None, is not None) and an HTTP status code.
    """
    if value is None:
        logger.error(error_message)
        if not skip:
            return error_message, 400
    return True, 200


def check_instance(obj, instance, error_message: str = None, skip: bool = False) -> tuple[bool, int] | tuple[str, int]:
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
            return error_message, 400
    return True, 200
