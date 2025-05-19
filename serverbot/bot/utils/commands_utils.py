import logging
from datetime import datetime

import requests
from django.core.exceptions import ObjectDoesNotExist
import logging
import json
import os

from django.db import transaction
from django.db.models import QuerySet

from ..config import init_config
from ..config.init_config import Configuration
from ..models import Command, Client, UserSettings
from .utils import check_None, check_instance
from .clients_utils import send_client_get_request
from . import user_utils, clients_utils

logger = logging.getLogger(__name__)


# Utility function to get a command by ID
def get_command_by_id(command_id: str) -> tuple[Command | str, int]:
    """
    Retrieves a command instance by its ID.

    Args:
        command_id (str): The unique identifier of the command.

    Returns:
        Command: The Command object if found, None otherwise.
    """
    # Check the parameters
    if not isinstance(command_id, str):
        logger.error(f"Invalid type for command_id: expected str, got {type(command_id)}")
        return f"Invalid type for command_id: expected str, got {type(command_id)}", 400

    try:
        command = Command.objects.get(command_id=command_id)
        return command, 200
    except ObjectDoesNotExist:
        logger.warning(f"Command with ID '{command_id}' not found.")
        return f"Command with ID '{command_id}' not found.", 404
    except Exception as e:
        logger.error(f"Error retrieving command '{command_id}': {e}", exc_info=True)
        return f"Error retrieving command '{command_id}': {e}", 500


# Utility function to get the command list from a client
def get_command_list(parameters: dict) -> tuple[QuerySet[Command] | str, int]:
    """
    Retrieves the command list from the client application.
    This function sends a GET request to the client and returns the response.
    Args:
        parameters (dict): A dictionary containing the parameters for the request.
                           Receives the client_id.
    Returns:
        tuple: A tuple containing the response data and the HTTP status code.
    """
    # Check if the parameters dictionary contains the expected keys and types
    expected_types = {
        "client_id": int,
    }
    for key, expected_type in expected_types.items():
        if key in parameters and not isinstance(parameters[key], expected_type):
            return f"Invalid type for parameter {key}: expected {expected_type}, got {type(parameters[key])}", 400
    # Gather the parameters from the request in a dictionary and ignore the rest
    parameters = {key: value for key, value in parameters.items() if key in expected_types}
    # Get the client object by ID
    client, code = clients_utils.get_client_by_id(parameters["client_id"])
    if code != 200:
        logger.error(f"Client with ID {parameters['client_id']} not found.")
        return client, code  # Return an error message if the client is not found

    # Get all the commands from the database
    try:
        commands = Command.objects.filter(client=client)
        return commands, 200  # Return the command list and status code
    except ObjectDoesNotExist:
        logger.warning(f"No commands found for client {client}.")
        return f"No commands found for client {client}.", 404
    except Exception as e:
        logger.error(f"Error retrieving commands for client {client}: {e}", exc_info=True)
        return f"Error retrieving commands for client {client}: {e}", 500


# Get the command list for a specific user from the database. Uses get_command_list for each client.
def get_command_list_by_user(user_id: int) -> tuple[list[Command], int] | tuple[str, int]:
    """
    Retrieves the command list for a specific user from the database.

    Args:
        user_id (int): The ID of the user whose command list is to be retrieved.

    Returns:
        tuple: A tuple containing the command list (as a dictionary) and the HTTP status code.
               If the user is not found, returns an error message and status code.
    """
    try:
        # Get the clients where the user is allowed
        clients, code = clients_utils.get_clients_by_user(user_id)
        if code != 200:
            logger.error(f"User with ID {user_id} not found.")
            return clients, 404

        # Retrieve the command list from each client
        command_list = []
        for client in clients:
            # Get the command list from the database, assuming the commands on the client are synchronized with the database
            commands, code = get_command_list({'client_id': client.id})
            if code != 200:
                logger.error(f"Error retrieving command list from client {client.id}: {commands}")
                continue  # Skip this client if there's an error

            # Add commands to the command list
            command_list.extend(commands)

        return command_list, 200  # Return the command list and status code

    except ObjectDoesNotExist:
        logger.error(f"User with ID {user_id} not found.")
        return "User not found.", 404  # Return error message and status code


# Utility function to synchronize a command entry from a dictionary with the database.
def sync_command_from_dict(command_id: str, details: dict) -> tuple[Command | str, int]:
    """
    Synchronizes a single command entry from a dictionary with the database.
    Creates or updates a Command object based on the provided details.
    Commands are vinculated to a client. The database contains all the available commands from every client on the local network.

    Args:
        command_id (str): The unique identifier for the command (the key from the JSON).
        details (dict): A dictionary containing the command's details (name, description, args).

    Returns:
        Command or None: The created or updated Command object on success, None on failure.
    """
    # Ensure essential keys exist in the details dictionary
    expected_types = {
        "name": str,
        "description": str,
        "args": list,
    }
    for key, expected_type in expected_types.items():
        if key not in details or not isinstance(details[key], expected_type):
            logger.error(f"sync_command_from_dict() - Invalid type for '{key}': expected {expected_type}, got {type(details[key])}")
            return f"sync_command_from_dict() - Invalid type for '{key}': expected {expected_type}, got {type(details[key])}", 400

    # Extract command details
    parameters = {
        "name": details["name"],
        "description": details["description"],
        "args": details["args"],
    }

    try:
        # Use get_or_create to find an existing command or create a new one
        command, created = Command.objects.get_or_create(
            command_id=command_id,
            defaults={
                'name': details['name'],
                'description': details['description'],
                'args': details['args']
            }
        )
        # If created is True, notify a new command was created
        if created:
            logger.debug(f"sync_command_from_dict() - Created new command: {command_id}")
            return command, 201  # Return the newly created command object
        else:
            # Check if the existing command's details need updating
            # Compare name, description, handler and args
            if command.name != parameters['name'] or command.description != parameters['description'] or command.args != parameters['args']:
                command.name = parameters['name']
                command.description = parameters['description']
                command.args = parameters['args']
                command.save()  # Save the changes to the database
                logger.info(f"Updated existing command: {command_id}")
            # Case 1: Exists and is identical - implicitly handled by get_or_create not updating defaults
            return command, 200  # Return the existing (or updated) command object
    except ObjectDoesNotExist:
        # Handle the case where a Command with the given command_id does not exist
        logger.warning(f"Command with ID '{command_id}' not found in the database. No action taken.")
        return f"Command with ID '{command_id}' not found in the database.", 404
    except Exception as e:
        # Catch any database-related errors during get_or_create or save
        logger.error(f"Error processing command {command_id} during DB operation: {e}", exc_info=True)
        # This validation returns a None as skipping the command.
        return f"Error processing command {command_id} during DB operation: {e}", 500  # Indicate failure to process this specific command


# Utility function to update the command list for a specific client. Uses sync_command_from_dict for each command.
def update_commands_list(client_obj: Client, command_dict: dict) -> bool:
    """
    Synchronizes the command list for a specific client in the database
    based on a dictionary received from the client application.

    This function handles creating, updating, and deleting Command objects
    for the given client.

    Args:
        client_obj (Client): The Client object representing the client sending the command list.
        command_dict (dict): A dictionary where keys are command_id strings
                             and values are dictionaries containing command details
                             (e.g., {'name': '...', 'description': '...', 'args': [...]}).

    Returns:
        bool: True if the synchronization process completed without critical errors,
              False otherwise. Note: Individual command processing errors might be logged
              without causing the entire function to return False.
    """
    check_None(client_obj, "update_command_list() - Received None client object.")
    check_None(command_dict, "update_command_list() - Received None command_dict.")

    check_instance(client_obj, Client, "update_command_list() - Received invalid client object.")
    check_instance(command_dict, dict,
                   f"update_command_list() - Invalid command_dict format provided. Expected a dictionary, got {type(command_dict)}.")

    logger.info(f"Starting command list synchronization for client: {client_obj}")

    try:
        # Use a transaction to ensure atomicity: either all changes succeed or none do.
        with transaction.atomic():
            # Get all existing command_ids for this client from the database
            existing_commands_qs = Command.objects.filter(client=client_obj)
            existing_command_ids = set(existing_commands_qs.values_list('command_id', flat=True))

            # Get command_ids from the received dictionary
            received_command_ids = set(command_dict.keys())

            # --- Process received commands (Create or Update) using the helper function ---
            for command_id, details in command_dict.items():
                # Call the sync_command_from_dict helper function for each command
                # Pass the client_obj to link the command correctly
                synced_command = sync_command_from_dict(command_id, details)

                # The helper function logs errors internally and returns None on failure
                if synced_command is None:
                    logger.warning(f"Failed to sync command '{command_id}' for client {client_obj}. Skipping.")
                    # Continue processing other commands even if one fails to sync

            # --- Delete commands not in the received dictionary ---
            commands_to_delete_ids = existing_command_ids - received_command_ids
            if commands_to_delete_ids:
                # Filter commands for this specific client before deleting
                deleted_count, _ = existing_commands_qs.filter(command_id__in=commands_to_delete_ids).delete()
                logger.info(
                    f"Deleted {deleted_count} commands for client {client_obj} not found in received list: {commands_to_delete_ids}")
            else:
                logger.info(f"No commands to delete for client {client_obj}.")

        logger.info(f"Command list synchronization completed for client: {client_obj}")
        return True  # Indicate overall success

    except Exception as e:
        # Catch any exceptions that occur outside the per-command loop (e.g., transaction error)
        logger.error(f"An unexpected error occurred during command list synchronization for client {client_obj}: {e}",
                     exc_info=True)
        return False  # Indicate overall failure


# Utility function to remove a command from the database by its ID
def remove_command_by_id(command_id: str):
    """
    Removes a Command object from the database based on its command_id.

    Args:
        command_id (str): The unique identifier of the command to remove.

    Returns:
        bool: True if the command was found and deleted, False otherwise.
    """
    logger.info(f"Attempting to remove command with ID: {command_id}")

    try:
        # Get the Command object by its command_id
        command = Command.get_command_by_id(command_id)

        # Delete the command object
        command.delete()

        logger.info(f"Successfully removed command with ID: {command_id}")
        return True  # Indicate successful deletion

    except ObjectDoesNotExist:
        # Handle the case where a Command with the given command_id does not exist
        logger.warning(f"Command with ID '{command_id}' not found in the database. No action taken.")
        return False  # Indicate that the command was not found

    except Exception as e:
        # Catch any other potential database-related errors during deletion
        logger.error(f"Error removing command with ID {command_id}: {e}", exc_info=True)
        # Returning False indicates failure to delete due to an error.
        return False  # Indicate failure due to an error


# Utility function to get the command list from a client. Sends a GET request to the client and returns the response with a dict of commands.
def get_command_list_from_client(parameters: dict) -> tuple[dict | str, int]:
    """
    Retrieves the command list from a client application.
    This function sends a GET request to the client and returns the response.

    Args:
        parameters (dict): Receives the client_id.

    Returns:
        tuple: A tuple containing the response data and the HTTP status code.
    """
    # Check if the parameters dictionary contains the expected keys and types
    expected_types = {
        "client_id": int,
    }
    for key, expected_type in expected_types.items():
        if key not in parameters or not isinstance(parameters[key], expected_type):
            return f"Invalid type for parameter {key}: expected {expected_type}, got {type(parameters[key])}", 400

    # Gather the parameters from the request in a dictionary and ignore the rest
    parameters = {key: value for key, value in parameters.items() if key in expected_types}

    # Get the client object by ID
    client, code = clients_utils.get_client_by_id(parameters["client_id"])
    if code != 200:
        logger.error(f"Client with ID {parameters['client_id']} not found.")
        return client, code  # Return an error message if the client is not found

    # Send a GET request to the client to retrieve the command list
    try:
        response = send_client_get_request(client.id, "command_list")
        if response.status_code == 200:
            command_list = json.loads(response.text)
            return command_list, 200  # Return the command list and status code
        else:
            logger.error(f"Error retrieving command list from client {client.id}: {response.status_code}")
            return f"Error retrieving command list from client {client.id}: {response.status_code}", response.status_code
    except requests.RequestException as e:
        logger.error(f"Request error while retrieving command list from client {client.id}: {e}", exc_info=True)
        return f"Request error while retrieving command list from client {client.id}: {e}", 500  # Internal Server Error


# Get last update of the command list
def get_last_command_update() -> datetime:
    """
    Retrieves the last update timestamp of the command list. It's stored in the 'configuration.ini' file, under the cathegory 'SystemStatistics'.

    Returns:
       datetime : The last update timestamp.
    """
    updated_time: str = Configuration["SystemStatistics"]["last_command_update"]

