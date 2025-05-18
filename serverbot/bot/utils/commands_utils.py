import logging

import requests
from django.core.exceptions import ObjectDoesNotExist
import logging
import json
import os

from django.db import transaction

from ..models import Command, Client, UserSettings
from .utils import send_client_get_request, check_None, check_instance
from . import user_utils, clients_utils

logger = logging.getLogger(__name__)


# Get the command list for a specific user
def get_command_list_by_user(user_id: int) -> tuple[dict, int] | tuple[str, int]:
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
        command_list = {}
        for client in clients:
            # Get the command list from the database, assuming the commands on the client are synchronized with the database
            # Get all the commands from the database
            commands = Command.objects.all()
            # Filter the commands based on the client
            commands = [command for command in commands if command.client == client]
            # Add commands to the command list
            for command in commands:
                command_list[command.command_id] = command

        return command_list, 200  # Return the command list and status code

    except ObjectDoesNotExist:
        logger.error(f"User with ID {user_id} not found.")
        return "User not found.", 404  # Return error message and status code


# Get the clients for an specific user
def sync_command_from_dict(command_id: str, details: dict):
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
    # These fields are required to create or update a Command instance
    name = details.get('name')
    description = details.get('description')
    args = details.get('args', [])  # Get args, default to empty list if missing

    # Basic validation of the dictionary content
    check_None(name, "sync_command_from_dict() - Received None name.")
    check_None(description, "sync_command_from_dict() - Received None description.")
    check_None(args, "sync_command_from_dict() - Received None args.")

    # Validate args format if provided. Ensure args is a list and all elements are strings
    check_instance(args, list, "sync_command_from_dict() - args is not a list.")

    try:
        # Use get_or_create to find an existing command or create a new one
        command, created = Command.objects.get_or_create(
            command_id=command_id,
            defaults={
                'name': name,
                'description': description,
                'args': args  # Save the args list to the JSONField
            }
        )
        # If created is True, notify a new command was created
        if created:
            logger.debug(f"sync_command_from_dict() - Created new command: {command_id}")
            return command  # Return the newly created command object
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
            return command  # Return the existing (or updated) command object

    except Exception as e:
        # Catch any database-related errors during get_or_create or save
        logger.error(f"Error processing command {command_id} during DB operation: {e}", exc_info=True)
        # This validation returns a None as skipping the command.
        return None  # Indicate failure to process this specific command


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


# Utility function to get the command list from a client
# def get_command_list() -> tuple[dict, int]:
#     """
#     Retrieves the command list from the client application.
#     This function sends a GET request to the client and returns the response.
#
#     Returns:
#         tuple: A tuple containing the response data and the HTTP status code.
#     """
#     # Define the URL for the client API endpoint
#     url = f"http://{os.getenv('CLIENT_IP')}/api/commands/list"
#     logger.debug(f"Sending GET request to client at {url}")
#
#     try:
#         # Get commands from the database
#         # Get the clients for that user
#         #clients =
#         client_obj = Client.get_client_by_id(1)  # Assuming a single client for simplicity
#         # Check if the response is successful (status code 200)
#         if response.status_code == 200:
#             return response.json(), 200  # Return JSON data and status code
#         else:
#             logger.error(f"Failed to retrieve command list from client. Status code: {response.status_code}")
#             return None, response.status_code  # Return None and status code on failure
#
#     except requests.RequestException as e:
#         # Handle any exceptions that occur during the request
#         logger.error(f"Error retrieving command list from client: {e}", exc_info=True)
#         return None, 500  # Return None and status code 500 on error
