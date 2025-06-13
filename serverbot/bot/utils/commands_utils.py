import logging
from datetime import datetime
from typing import Dict, Optional

import requests
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
import logging
import json
import os

from django.db import transaction
from django.db.models import QuerySet

from ..config import init_config, config
from ..config.init_config import Configuration
from ..models import Command, Client, UserSettings
from .utils import check_None, check_instance
from .clients_utils import send_client_get_request
from . import user_utils, clients_utils

logger = logging.getLogger(__name__)


# ---- From Data Base ----
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
        command = Command.objects.get(pk=command_id)
        return command, 200
    except ObjectDoesNotExist:
        logger.warning(f"Command with ID '{command_id}' not found.")
        return f"Command with ID '{command_id}' not found.", 404
    except Exception as e:
        logger.error(f"Error retrieving command '{command_id}': {e}", exc_info=True)
        return f"Error retrieving command '{command_id}': {e}", 500


# Get command list by client ID from the database.
def get_command_list_by_client(client_id: int) -> tuple[list[Command], int] | tuple[str, int]:
    """
    Retrieves the command list for a specific client from the database.

    Args:
        client_id (int): The ID of the client whose command list is to be retrieved.

    Returns:
        tuple: A tuple containing the command list (as a dictionary) and the HTTP status code.
               If the client is not found, returns an error message and status code.
    """
    try:
        # Get the client by ID
        client, code = clients_utils.get_client_by_id(client_id)
        if code != 200:
            logger.error(f"Client with ID {client_id} not found.")
            return client, 404  # Return an error message if the client is not found

        # Retrieve the command list from the database
        commands_list = Command.objects.filter(client=client)
        if not commands_list.exists():
            logger.warning(f"No commands found for client {client_id}.")
            return [], 200  # Return an empty list if no commands are found

        return commands_list, 200  # Return the command list and status code

    except Exception as e:
        logger.error(f"Error retrieving commands for client {client_id}: {e}", exc_info=True)
        return f"Error retrieving commands for client {client_id}: {e}", 500  # Internal Server Error


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
            try:
                commands_list, code = get_command_list_by_client(client.id)
                if code != 200:
                    logger.error(f"Error retrieving commands for client {client.id}: {commands_list}")
                    return commands_list, code
            except Exception as e:
                logger.error(f"Error retrieving commands for client {client.id}: {e}", exc_info=True)
                return f"Error retrieving commands for client {client.id}: {e}", 500

            # Add commands to the command list
            command_list.extend(commands_list)

        return command_list, 200  # Return the command list and status code

    except ObjectDoesNotExist:
        logger.error(f"User with ID {user_id} not found.")
        return "User not found.", 404  # Return error message and status code


# Utility function to synchronize a command entry from a dictionary with the database.
def upload_command_from_dict(client: Client, name: str, title: str, description: str, args: list,
                             command_id: Optional[str] = None) -> tuple[Command | str, int]:
    """
    Synchronizes a single command entry from a dictionary with the database.
    Creates or updates a Command object based on the provided details.
    Commands are vinculated to a client. The database contains all the available commands from every client on the local network.

    Args:
        client (Client): The Client object to which the command belongs.
        name (str): The name of the command.
        title (str): The title of the command.
        description (str): A brief description of the command.
        args (list): A list of argument types for the command.
        command_id (Optional[str]): The unique identifier for the command. If None, a new command will be created.

    Returns:
        Command or None: The created or updated Command object on success, None on failure.
    """

    try:
        # Use get_or_create to find an existing command or create a new one
        if not command_id:
            # If command_id is not provided, create a new command on the DB
            command, created = Command.objects.get_or_create(
                client=client,
                name=name,
                title=title,
                description=description,
                args=args
            )
        command, created = Command.objects.get_or_create(
            command_id=command_id,
            client=client,
            name=name,
            title=title,
            description=description,
            args=args
        )
        # If created is True, notify a new command was created
        if created:
            logger.debug(f"sync_command_from_dict() - Created new command: {command_id}")
            return command, 201  # Return the newly created command object
        else:
            # Check if the existing command's details need updating
            # Compare name, description, handler and args
            if command.name != name or command.description != description or command.args != args:
                command.name = name
                command.description = description
                command.args = args
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


# ---- From Client ----

# Utility function to update the command list for a specific client. Uses sync_command_from_dict for each command.
def sync_commands_list(user: User) -> tuple[str, int]:
    """
    Synchronizes the command list for a specific client in the database.

    This function handles creating, updating, and deleting Command objects
    for the request user.

    Returns:
        tuple: A tuple containing a success or error message and HTTP status code.
    """
    message, code = check_None(user, "update_command_list() - Received None client object.")
    if code != 200:
        logger.error(message)
        return message, code
    message, code = check_instance(user, User, "update_command_list() - Received invalid client object.")
    if code != 200:
        logger.error(message)
        return message, code

    clients, code = clients_utils.get_clients_by_user(user.pk)
    if code != 200:
        logger.error(f"Failed to retrieve clients for user {user.pk}: {clients}")
        return clients, code

    # Skips the client if there is some error retrieving the commands
    for client_obj in clients:
        # Synchronize the command list for each client
        logger.info(f"Starting command list synchronization for client: {client_obj}")

        # Send GET request to the client to retrieve the current command list
        response, code = clients_utils.send_client_get_request(client_obj, "api/commands/list")
        if code != 200:
            logger.error(f"Failed to retrieve command list from client {client_obj}: {response}")
            continue  # Return the error message and status code

        logger.debug(f"Received command list from client {client_obj}: {response}")
        logging.info(f"Updating command list for client {client_obj}.")

        # Get commandsd from the 'data' key in the response
        command_list = response["data"]
        if not isinstance(command_list, list):
            logger.error(f"Invalid command list format received from client {client_obj}. Expected a list.")
            continue

        for command in command_list:
            # Check if the command has the required keys
            required_keys = ["title", "name", "description", "args_types"]
            for key in required_keys:
                if key not in command:
                    logger.error(f"Command missing required key '{key}': {command}")
                    continue
            # Prepare the command details for synchronization
            details = {
                "client": client_obj,  # The client object to which the command belongs
                "name": command["name"],
                "title": command["title"],
                "description": command["description"],
                "args": command.get("args_types", []),  # Default to empty list if not provided
            }
            # Synchronize the command with the database
            result, code = upload_command_from_dict(**details)
            if code != 200:
                logger.error(f"Error synchronizing command {command}: {result}")
                continue

    return f"Command list for client {client_obj} updated successfully.", 200  # Indicate that the command list was successfully updated


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
        client: str
        logger.error(f"Client with ID {parameters['client_id']} not found.")
        return client, code  # Return an error message if the client is not found
    client: Client

    # Send a GET request to the client to retrieve the command list
    api_endpoint = f"api/commands/list"
    try:
        response, code = send_client_get_request(client.pk, api_endpoint)
        if code == 200:
            command_list = json.loads(response.text)
            logger.info(f"Successfully retrieved command list from client {client.pk}: {command_list}")
            return command_list, 200  # Return the command list and status code
        else:
            logger.error(f"Error retrieving command list from client {client.pk}: {response.status_code}")
            return f"Error retrieving command list from client {client.pk}: {response.status_code}", response.status_code
    except requests.RequestException as e:
        logger.error(f"Request error while retrieving command list from client {client.pk}: {e}", exc_info=True)
        return f"Request error while retrieving command list from client {client.pk}: {e}", 500  # Internal Server Error


# Get last update of the command list
def get_last_command_update() -> datetime:
    """
    Retrieves the last update timestamp of the command list. It's stored in the 'configuration.ini' file, under the cathegory 'SystemStatistics'.

    Returns:
       datetime : The last update timestamp.
    """
    updated_time: str = config.configuration["SystemStatistics"]["last_command_update"]
    if updated_time:
        try:
            return datetime.fromisoformat(updated_time)
        except ValueError as e:
            logger.error(f"Invalid date format in configuration: {updated_time}. Error: {e}")
    else:
        logger.warning("No last command update timestamp found in configuration.")
