import logging

from django.core.exceptions import ObjectDoesNotExist
import logging
import json
import os
from ..config.config import COMMANDS_JSON_PATH
from ..models import Command


logger = logging.getLogger(__name__)


def sync_command_from_dict(command_id: str, details: dict):
    """
    Synchronizes a single command entry from a dictionary with the database.
    Creates or updates a Command object based on the provided details.
    Commands are vinculated to a client. The database contains all the available commands from every client on the local network.

    Args:
        command_id (str): The unique identifier for the command (the key from the JSON).
        details (dict): A dictionary containing the command's details (name, description, args, handler).

    Returns:
        Command or None: The created or updated Command object on success, None on failure.
    """
    # Ensure essential keys exist in the details dictionary
    # These fields are required to create or update a Command instance
    name = details.get('name')
    description = details.get('description')
    handler_path = details.get('handler')  # handler is used by the execution logic, not stored in Command model
    args = details.get('args', [])  # Get args, default to empty list if missing

    # Basic validation of the dictionary content
    if not name or not description or not handler_path:
        logger.warning(
            f"Skipping command '{command_id}' due to missing 'name', 'description', or 'handler' in details dictionary.")
        # This validation returns a None as skipping the command.
        return None  # Indicate failure to process this specific command

    # Validate args format if provided. Ensure args is a list and all elements are strings
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        logger.warning(
            f"Skipping command '{command_id}' due to invalid 'args' format. Expected a list of strings. ['String', 'Integer', 'Boolean', 'Float']")
        # This validation returns a None as skipping the command.
        return None  # Indicate failure to process this specific command

    try:
        # Use get_or_create to find an existing command or create a new one
        command, created = Command.objects.get_or_create(
            command_id=command_id,
            defaults={
                'name': name,
                'description': description,
                'handler': handler_path,
                'args': args  # Save the args list to the JSONField
            }
        )
        # If created is True, notify a new command was created
        if created:
            logger.info(f"Created new command: {command_id}")
            return command  # Return the newly created command object
        else:
            # Check if the existing command's details need updating
            # Compare name, description, handler and args
            if command.name != name or command.description != description or command.args != args or command.handler != handler_path:
                command.name = name
                command.handler = handler_path
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
        command = Command.objects.get(command_id=command_id)

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


def load_commands_from_json():
    """
    Reads commands from a JSON file and synchronizes them with the database.
    Handles creation, update, and deletion of Command objects based on the JSON content.
    """
    logger.info(f"Attempting to load commands from {COMMANDS_JSON_PATH}")

    # If the JSON file does not exist, create it with an example
    if not os.path.exists(COMMANDS_JSON_PATH):
        logger.warning(f"Commands JSON file not found at: {COMMANDS_JSON_PATH}. Creating with default content.")

        # Define the default content for the JSON file
        default_commands_data = {
            "hello_world": {
                "name": "Hello World",  # Added a name for the command
                "description": "Sends a simple hello world message from the server.",
                "args": [],  # There are no arguments for this command
                "handler": "hello_world"  # Points to commands/hello_world.py
            }
        }
        # Ensure the directory for the JSON file exists
        COMMANDS_JSON_DIR = os.path.dirname(COMMANDS_JSON_PATH)
        os.makedirs(COMMANDS_JSON_DIR, exist_ok=True)

        try:
            # Write the default content to the file
            with open(COMMANDS_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_commands_data, f, indent=2)  # Use indent for readability
            logger.info(f"Created default commands JSON file at: {COMMANDS_JSON_PATH}")

        except Exception as e:
            logger.error(f"Error creating default commands JSON file at {COMMANDS_JSON_PATH}: {e}", exc_info=True)
            # If file creation fails, we can't proceed.
            return False  # Indicate failure
        # After creating the file, proceed to load commands from it
        # The rest of the function will now read the newly created file.

    try:
        with open(COMMANDS_JSON_PATH, 'r', encoding='utf-8') as f:
            commands_data = json.load(f)
        logger.info("Successfully read commands JSON file.")

    except json.JSONDecodeError as e:
        # Handle JSON decoding errors by raising a ValueError
        logger.error(f"Error decoding JSON from {COMMANDS_JSON_PATH}. Please check the file format.", exc_info=True)
        # Raising an exception here is appropriate as invalid JSON is a critical configuration error.
        raise ValueError(f"Invalid JSON format in commands file: {COMMANDS_JSON_PATH}") from e

    except Exception as e:
        logger.error(f"An unexpected error occurred while reading {COMMANDS_JSON_PATH}: {e}", exc_info=True)
        # Handle other file reading errors
        raise IOError(f"An error occurred while reading commands file: {COMMANDS_JSON_PATH}") from e

    # Get all existing command_ids from the database
    existing_command_ids = set(Command.objects.values_list('command_id', flat=True))
    json_command_ids = set(commands_data.keys())

    # Create new or Update existing commands
    for command_id, details in commands_data.items():
        name = details.get('name', command_id)
        description = details.get('description', 'No description provided.')
        handler = details.get('handler')
        args = details.get('args', [])

        try:
            command, created = Command.objects.get_or_create(
                command_id=command_id,
                defaults={
                    'name': name,
                    'description': description,
                    'handler': handler,
                    'args': args
                }
            )

            if created:
                logger.info(f"Created new command: {command_id}")
            else:
                # Check if existing command needs updating (Case 2)
                if command.name != name or command.description != description or command.args != args or command.handler != handler:
                    command.name = name
                    command.description = description
                    command.handler = handler
                    command.args = args
                    command.save()
                    logger.info(f"Updated existing command: {command_id}")
                # Case 1: Exists and is identical - implicitly handled by get_or_create not updating defaults

        except Exception as e:
            logger.error(f"Error processing command {command_id}: {e}", exc_info=True)
            # The command creation or update failed, log the error. The command is skipped

    # Delete commands not in JSON
    commands_to_delete_ids = existing_command_ids - json_command_ids
    if commands_to_delete_ids:
        for command_id in commands_to_delete_ids:
            logger.info(f"Command with ID '{command_id}' not found in JSON. Deleting from database.")
            # Call the function to remove the command
            remove_command_by_id(command_id)  # Call the function to remove the command
    else:
        logger.info("No commands to delete from the database.")

    logger.info("Command synchronization with database completed.")
    return True  # Indicate success


def get_command_by_id(command_id: str) -> Command | None:
    """
    Retrieves a Command object from the database based on its command_id.

    Args:
        command_id (str): The unique identifier of the command to retrieve.

    Returns:
        Command or None: The Command object if found, None otherwise.
    """
    try:
        # Get the Command object by its command_id
        command: Command = Command.objects.get(command_id=command_id)
        return command  # Return the found command object

    except ObjectDoesNotExist:
        # Handle the case where a Command with the given command_id does not exist
        logger.warning(f"Command with ID '{command_id}' not found in the database.")
        return None  # Indicate that the command was not found


def get_command_list():
    """
    Retrieves all Command objects from the database.

    Returns:
        list: A list of Command objects.
    """
    try:
        # Get all Command objects from the database
        commands = Command.objects.all()
        commands_list = [str(command) for command in commands]  # Create a list of command objects
        return commands_list  # Return the list of command objects

    except Exception as e:
        logger.error(f"Error retrieving command list: {e}", exc_info=True)
        return []  # Return an empty list in case of error