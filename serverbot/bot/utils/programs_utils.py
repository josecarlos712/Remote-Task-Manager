import subprocess
import requests
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from django.db import transaction
from django.http import JsonResponse

from .APIResponse import InternalErrorResponse
from .utils import check_None, check_instance, send_client_get_request
from ..models import Program, Client
import json
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

processes = {}
processes_status = {}


def refresh_processes_status(client_id: int):
    """
    Refreshes the status of all processes running on the client application.

    args:
        client_id (int): The ID of the client whose processes are to be refreshed.
    returns:
        JsonResponse: A JSON response containing the status of the processes.
        or
        program_status_data (dict): A dictionary containing the status of the processes.
        and
        status_code (int): The HTTP status code of the response.
    """
    # --- Make GET request to the client's '/api/program/status' endpoint ---
    client_status_endpoint = "api/program/status"  # The endpoint on the client application

    # logger.debug(f"refresh_processes_status() - Making GET request to client {client_obj} at /{client_status_endpoint}")

    # Use the helper function to send the GET request to the client
    program_status_data, client_status_code = send_client_get_request(client_id, client_status_endpoint)

    # Handle errors from the GET request to the client
    if program_status_data is None:
        logger.error(
            f"refresh_processes_status() - Failed to get program status from client {client_id}. Client status code: {client_status_code}")
        # send_client_get_request already logs specific errors (timeout, connection, http, json)
        return InternalErrorResponse(f"Client responded with status {client_status_code}").to_response(), client_status_code

    # Assuming the client's response is a list of program status dictionaries
    if not isinstance(program_status_data, dict):
        logger.error(
            f"refresh_processes_status() - Client {client_id} returned invalid status data format. Expected a dict, got {type(program_status_data)}.")
        return InternalErrorResponse(
            f"Client {client_id} returned invalid status data format. Expected a dict, got {type(program_status_data)}.").to_response(), 400  # Bad Request

    return program_status_data, 200  # Return the status data and HTTP status code


def sync_programs_from_json(json_file_path):
    messages = []
    # Read JSON file
    with open(json_file_path, 'r') as file:
        json_data = json.load(file)

    # Get all programs from the database
    db_programs = Program.objects.all()

    # Track names to determine which programs to keep or delete
    json_program_names = set()
    db_program_names = set(program.name for program in db_programs)

    # Use a transaction for atomicity, either all changes happen or none
    with transaction.atomic():
        # Iterate over the programs in the JSON file
        for json_program in json_data:
            program_name = json_program['name']
            json_program_names.add(program_name)

            # Try to find a matching program in the database by 'name'
            try:
                db_program = Program.objects.get(name=program_name)

                # Check if the existing DB program matches the JSON program using 'is_equal'
                if not db_program.is_equal(json_program):
                    # If the program exists but is different, update it
                    db_program.title = json_program['title']
                    db_program.path = json_program['path']
                    db_program.program = json_program.get('program', 'None')
                    db_program.description = json_program.get('description', 'None')
                    db_program.save()
                    messages.append(f"Program modified. Modifying... {db_program.name}")
                # else:
                # messages.append(f"Program already exists. Skipping... {db_program.name}")
            except Program.DoesNotExist:
                messages.append(f"Program not exist. Creating... {program_name}")
                # If the program does not exist in the database, create it
                Program.objects.create(
                    name=program_name,
                    title=json_program['title'],
                    path=json_program['path'],
                    program=json_program.get('program', 'None'),
                    description=json_program.get('description', 'None')
                )

        # Find and delete programs in the DB that are not in the JSON
        programs_to_delete = db_program_names - json_program_names
        messages.append(f"Programs to delete: {programs_to_delete if programs_to_delete.__len__() > 0 else 'None'}")
        Program.objects.filter(name__in=programs_to_delete).delete()
    return messages


def sync_program_from_dict(client_obj: Client, program_data: dict):
    """
    Synchronizes a single program entry from a dictionary with the database,
    linking it to a specific client.

    Uses the client and the program's 'name' as the unique identifier for lookup.

    Args:
        client_obj (Client): The Client object this program belongs to.
        program_data (dict): A dictionary containing the program's details
                             (expected keys: 'name', 'title', 'description', 'available').

    Returns:
        Program or None: The created or updated Program object on success, None on failure.
    """
    if check_instance(client_obj, Client,
                      f"sync_program_from_dict() - Invalid client_obj provided: {client_obj}"): return None
    if check_instance(program_data, dict,
                      f"sync_program_from_dict() - Invalid program_data format provided. Expected a dictionary, got {type(program_data)}."): return None

    # Ensure essential keys exist in the details dictionary
    # These fields are required to create or update a Program instance
    name = program_data.get('name')
    title = program_data.get('title')
    description = program_data.get('description')  # description can be None based on model default

    if check_None(name,
                  f"sync_program_from_dict() - Skipping program for client {client_obj} due to None 'name' in data."): return None
    if check_None(title,
                  f"sync_program_from_dict() - Skipping program '{name}' for client {client_obj} due to None 'title' in data."): return None

    # Validate 'description' type
    if check_instance(description, str,
                      f"sync_program_from_dict() - Skipping program '{name}' for client {client_obj} due to invalid 'description' format. Expected a string, got {type(description)}."): return None

    try:
        # Use get_or_create to find an existing program or create a new one for this client
        program, created = Program.objects.get_or_create(
            client=client_obj,  # Link to the client
            name=name,
            defaults={
                'title': title,
                'name': name,
                'description': description,  # Use the provided description (can be None)
            }
        )

        if created:
            logger.info(f"Created new program '{name}' for client {client_obj}.")
            return program  # Return the newly created program object
        else:
            # Check if the existing program's details need updating
            # Compare title, description, and available
            # Only update if the received data is different from what's in the DB
            needs_update = False
            if program.name != name:
                program.name = name
                needs_update = True
            if program.title != title:
                program.title = title
                needs_update = True
            # Update description only if there's new info
            if description is not None and program.description != description:
                program.description = description
                needs_update = True

            if needs_update:
                program.save()
                logger.info(f"Updated existing program '{name}' for client {client_obj}.")
            else:
                logger.debug(f"Program '{name}' for client {client_obj} is identical. Skipping update.")

            return program  # Return the existing (or updated) program object

    except Exception as e:
        # Catch any database-related errors during get_or_create or save
        logger.error(f"Error processing program '{name}' for client {client_obj} during DB operation: {e}",
                     exc_info=True)
        # Returning None indicates failure to process this specific program.
        return None  # Indicate failure to process this specific program


def update_existing_program(client_id: int, program_data: dict):
    """
    Updates an existing Program object in the database based on provided data.
    The program is identified by its client and name.
    Only updates fields that are present in the program_data dictionary.

    Args:
        client_id (int): The Client ID this program belongs to.
        program_data (dict): A dictionary containing the program's details to update.
                             Must include 'name' for lookup. Can include 'title',
                             'description', 'available', 'is_running', 'start_time',
                             'end_time'.

    Returns:
        tuple(Program/message(str) , status(bool)): The updated Program object on success, an error message if the program
                         is not found or an error occurs, and the success status.
    """
    # Initial validation using helper functions
    if check_instance(client_id, int,
                      f"update_existing_program() - Invalid client_obj provided: {client_id}"):
        return f"update_existing_program() - Invalid client_obj provided: {client_id}", False
    if check_instance(program_data, dict,
                      f"update_existing_program() - Invalid program_data format provided. Expected a dictionary, got {type(program_data)}."):
        return f"update_existing_program() - Invalid program_data format provided. Expected a dictionary, got {type(program_data)}.", False

    program_id = program_data.get('program_id')
    if check_None(program_id,
                  f"update_existing_program() - Missing 'program_id' in program_data for client {client_id}. Cannot update."):
        return f"update_existing_program() - Missing 'program_id' in program_data for client {client_id}. Cannot update.", False

    # Fetch the client object from the database using the provided client_id
    client_obj, status = Client.get_client_by_ID(client_id)
    if not status:
        return f"update_existing_program() - Client with ID {client_id} not found in the database. {client_obj}", False

    try:
        # Attempt to get the existing program for this client and name
        program = Program.objects.get(client=client_obj, pk=program_id)
        logger.debug(f"Attempting to update program '{program.name}' for client {client_obj}.")
        # Update fields based on provided data
        needs_save = False

        # Define updateable fields and their expected types
        updateable_fields = {
            'name': str,
            'title': str,
            'description': str,
            'available': bool,
            'is_running': bool,
            'start_time': (str, type(None)),  # Accept string (ISO format)
            'end_time': (str, type(None)),  # Accept string (ISO format)

            # 'client', 'updated', 'created' are not typically updated this way
        }

        for field_name, expected_type in updateable_fields.items():
            # Check if the field is present in the input data
            if field_name in program_data:
                field_value = program_data[field_name]

                # Validate the type of the provided value (optional but recommended)
                if not isinstance(field_value, expected_type):
                    logger.warning(
                        f"Skipping update for field '{field_name}' for program '{program.name}' due to invalid type. Expected {expected_type}, got {type(field_value)}.")
                    continue  # Skip this field and move to the next

                # Special handling for datetime fields if receiving strings
                if field_name in ['start_time', 'end_time'] and isinstance(field_value, str):
                    try:
                        # Attempt to parse ISO 8601 formatted string to datetime object
                        # If the string is empty, treat it as None
                        if field_value == "":
                            field_value = None
                        else:
                            # Assuming ISO 8601 format, adjust if needed
                            from django.utils.timezone import make_aware
                            # field_value = parse_datetime(field_value)
                            # Or using datetime.fromisoformat (requires Python 3.7+)
                            from datetime import datetime
                            field_value = datetime.fromisoformat(field_value)
                            # Make it timezone-aware if your project uses timezones
                            if settings.USE_TZ and field_value and field_value.tzinfo is None:
                                field_value = make_aware(field_value)

                    except ValueError:
                        logger.warning(
                            f"Skipping update for datetime field '{field_name}' for program '{program.name}' due to invalid string format: '{field_value}'")
                        continue  # Skip if datetime string is invalid

                # Check if the value is actually different before updating and marking for save
                current_value = getattr(program, field_name)

                # Handle comparison for datetime fields carefully (timezone awareness, None)
                if field_name in ['start_time', 'end_time']:
                    # Compare datetime objects
                    if current_value != field_value:
                        setattr(program, field_name, field_value)
                        needs_save = True
                        logger.debug(
                            f"Updating program '{program.name}' field '{field_name}' from '{current_value}' to '{field_value}'.")
                else:
                    # Compare other field types
                    if current_value != field_value:
                        setattr(program, field_name, field_value)
                        needs_save = True
                        logger.debug(
                            f"Updating program '{program.name}' field '{field_name}' from '{current_value}' to '{field_value}'.")

        # Save the changes to the database if any fields were updated
        if needs_save:
            program.save()
            logger.info(f"Successfully updated program '{program.name}' for client {client_obj}.")
        else:
            logger.debug(f"No updateable fields changed for program '{program.name}' for client {client_obj}.")

        return program  # Return the updated program object

    except ObjectDoesNotExist:
        # Handle the case where a program with the given client and name does not exist
        logger.warning(f"Program '{program.name}' for client {client_obj} not found in the database. Cannot update.")
        return None  # Indicate that the program was not found

    except MultipleObjectsReturned:
        # Should not happen if you have a UniqueConstraint on ['client', 'name']
        logger.error(f"Multiple programs found with name '{program.name}' for client {client_obj}. Database error?")
        return None  # Indicate a database error

    except Exception as e:
        # Catch any other potential database-related errors during retrieval or update
        logger.error(f"Error updating program '{program.name}' for client {client_obj}: {e}", exc_info=True)
        # Returning None indicates failure due to an error.
        return None  # Indicate failure due to an error


def update_programs_list(client_id: int, program_dict: dict) -> bool:
    """
    Synchronizes the program list for a specific client in the database
    based on a dictionary received from the client application.

    This function handles creating, updating, and deleting program objects
    for the given client.

    Args:
        client_id (int): The Client ID representing the client sending the program list.
        program_dict (dict): A dictionary where keys are program_id strings
                             and values are dictionaries containing program details
                             (e.g., {'name': '...', 'description': '...', 'available': True}).

    Returns:
        bool: True if the synchronization process completed without critical errors,
              False otherwise. Note: Individual program processing errors might be logged
              without causing the entire function to return False.
    """
    check_None(client_id, "update_program_list() - Received None client ID.")
    check_None(program_dict, "update_program_list() - Received None program_dict.")

    check_instance(client_id, int,
                   f"update_program_list() - Invalid client_id provided. Expected an integer, got {type(client_id)}.")
    check_instance(program_dict, dict,
                   f"update_program_list() - Invalid program_dict format provided. Expected a dictionary, got {type(program_dict)}.")

    # Fetch the client object from the database using the provided client_id
    client_obj = Client.get_client_by_ID(client_id)
    logger.info(f"Starting program list synchronization for client: {client_obj}")

    try:
        # Use a transaction to ensure atomicity: either all changes succeed or none do.
        with transaction.atomic():
            # Get all existing program_ids for this client from the database
            existing_programs_qs = Program.objects.filter(client=client_obj)
            existing_program_ids = set(existing_programs_qs.values_list('program_id', flat=True))

            # Get program_ids from the received dictionary
            received_program_ids = set(program_dict.keys())

            # --- Process received programs (Create or Update) using the helper function ---
            for program_id, details in program_dict.items():
                # Call the sync_program_from_dict helper function for each program
                # Pass the client_obj to link the program correctly
                synced_program = sync_program_from_dict(program_id, details)

                # The helper function logs errors internally and returns None on failure
                if synced_program is None:
                    logger.warning(f"Failed to sync program '{program_id}' for client {client_obj}. Skipping.")
                    # Continue processing other programs even if one fails to sync

            # --- Set 'available' to False for programs not in the received dictionary ---
            # Identify program names to set unavailable (existing names not present in the received list)
            program_names_to_set_unavailable = existing_program_ids - received_program_ids
            if program_names_to_set_unavailable:
                # Filter programs for this specific client by name and update their 'available' status
                updated_count = existing_programs_qs.filter(name__in=program_names_to_set_unavailable).update(
                    available=False)
                logger.info(
                    f"Set 'available' to False for {updated_count} programs for client {client_obj}. No information was found in received list: {program_names_to_set_unavailable}")
            else:
                logger.info(f"No programs to set unavailable for client {client_obj}.")

        logger.info(f"Program list synchronization completed for client: {client_obj}")
        return True  # Indicate overall success

    except Exception as e:
        # Catch any exceptions that occur outside the per-program loop (e.g., transaction error)
        logger.error(f"An unexpected error occurred during program list synchronization for client {client_obj}: {e}",
                     exc_info=True)
        return False  # Indicate overall failure


def get_program_by_id(program_id: str) -> Program | None:
    """
    Retrieves a program object from the database based on its program_id.

    Args:
        program_id (str): The unique identifier of the program to retrieve.

    Returns:
        program or None: The program object if found, None otherwise.
    """
    try:
        # Get the program object by its program_id
        program: Program = Program.objects.get(program_id=program_id)
        return program  # Return the found program object

    except ObjectDoesNotExist:
        # Handle the case where a program with the given program_id does not exist
        logger.warning(f"program with ID '{program_id}' not found in the database.")
        return None  # Indicate that the program was not found


def get_program_list(client_obj):
    """
    Sends a GET request to a client application to retrieve its list of programs.

    Args:
        client_obj (Client): The Django Client model instance representing the client.

    Returns:
        list or None: A list of program dictionaries received from the client,
                      or None if the request fails or the response is invalid.
                      Each dictionary is expected to represent a program
                      (e.g., {'program_id': '...', 'name': '...', ...}).
    """

    # TODO - Replace every check with check function
    check_None(client_obj, "get_client_programs() - Received None client object.")

    # URL for the client application's program list API endpoint
    programs_api_endpoint = "api/program/list"

    logger.debug(f"get_client_programs() - Sending GET request to {programs_api_endpoint} for client {client_obj}")

    # Send GET request to the client application
    response, status_code = send_client_get_request(client_obj, programs_api_endpoint)
    logger.debug(f"get_client_programs() - Received programs list from client {client_obj}: {response}")

    if response and status_code == 200:
        return response  # Return the list of programs if the request was successful
    else:
        logger.warning(
            f"get_client_programs() - Failed to retrieve programs from client {client_obj}. Status code: {status_code}")
        return None  # Return None if the request failed or the response was invalid
