import logging
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.utils import timezone

from .utils import check_None, check_instance
from ..models import Activity, Message, get_user_by_id
from .activity_utils import get_activity_by_id

# Get the User model
User = get_user_model()

logger = logging.getLogger(__name__)


#  Utility function to create a message in the database 
def create_message(parameters: dict) -> tuple[str, int] | tuple[Message, int]:
    """
    Create a message in the database.

    args: parameters (dict): Parameters for the message.
    {
        "user_id": int,      # Required
        "activity_id": int,  # Required
        "body": str,         # Optional, defaults to "" and blank=True in model
    }

    returns: tuple. (Message object/error message, status code).
    """
    logger.info("Attempting to create a new message.")
    # Check the parameters dictionary for the required keys and types
    # 'user_id' and 'activity_id' are required for lookup, 'body' is optional
    expected_types = {
        "user_id": int,
        "activity_id": int,
        "body": str,
        "created": timezone.datetime,
    }

    # Add created and updated fields to the parameters
    parameters["created"] = timezone.localtime()
    parameters["updated"] = timezone.localtime()

    # Check if the dictionary contains the expected keys and types
    for key, expected_type in expected_types.items():
        if key not in parameters:
            return f"Missing parameter: {key}", 400
        if not isinstance(parameters[key], expected_type):
            return f"Invalid type for parameter {key}: expected {expected_type}, got {type(parameters[key])}", 400

    # Check if the user exists in the database
    existing_user, code = get_user_by_id(parameters["user_id"])
    if code != 200:
        return existing_user, code  # Return the error message and status code if user not found

    # Get the activity by ID
    existing_activity, code = get_activity_by_id(parameters["activity_id"])
    if code != 200:
        return existing_activity, code  # Return the error message and status code if activity not found

    try:
        # Start a transaction to ensure atomicity
        with transaction.atomic():
            # Create the message
            message = Message.objects.create(
                user=existing_user,
                activity=existing_activity,
                body=parameters["body"],
                # created and updated fields will be set automatically by auto_now_add/default=timezone.now
            )
            logger.info(f"Message created successfully with ID: {message.pk}")
            return message, 201  # Created
    except Exception as e:
        logger.error(f"Error creating message: {e}", exc_info=True)
        return "There was an internal error creating the message", 500  # Internal Server Error


#  Utility function to get an existing message 
def get_message_by_id(message_id: int) -> tuple[str, int] | tuple[Message, int]:
    """
    Get an existing message from the database by its ID.

    args: message_id (int): ID of the message to be retrieved.

    returns: tuple. (Message object/error message, status code).
    """
    logger.info(f"Attempting to retrieve message with ID: {message_id}")
    # Check if the message_id is valid
    if not isinstance(message_id, int):
        return "Invalid message ID", 400  # Bad Request

    try:
        # Get the message object by its primary key (pk)
        existing_message = Message.objects.get(pk=message_id)
        # Convert datetime fields to the local time zone
        existing_message.created = timezone.localtime(existing_message.created)
        existing_message.updated = timezone.localtime(existing_message.updated)
        logger.debug(f"Message retrieved successfully with ID: {message_id}")
        return existing_message, 200  # OK

    except ObjectDoesNotExist:
        logger.warning(f"Message with ID '{message_id}' does not exist.")
        return f"Message with id {message_id} does not exist", 404  # Not Found

    except MultipleObjectsReturned:
        # Should not happen for primary key lookup, but included for robustness
        logger.error(f"Multiple messages found for ID '{message_id}'. Database error?")
        return f"Multiple messages found for ID '{message_id}'. Database error?", 500  # Internal Server Error

    except Exception as e:
        logger.error(f"Error retrieving message '{message_id}': {e}", exc_info=True)
        return f"Error retrieving message '{message_id}': {e}", 500  # Internal Server Error


#  Utility function to update an existing message 
def update_message(parameters: dict) -> tuple[str, int] | tuple[Message, int]:
    """
    Update an existing message in the database.

    args: message_id (int): ID of the message to be updated.
          parameters (dict): Parameters for the message.
    {
        "message_id": int,  # Required
        "body": str,         # Required
    }
    returns: tuple. (Message object/error message, status code).
    """
    # Check if the parameters dictionary contains the required keys
    expected_keys = {
        "message_id": int,
        "body": str
    }
    for key in expected_keys:
        if key not in parameters:
            return f"Missing parameter: {key}", 400
        elif not isinstance(parameters['message_id'], int):
            return f"Expected type {expected_keys['message_id']}, received {type(parameters['message_id'])}", 400
        elif not isinstance(parameters['body'], str):
            return f"Expected type {expected_keys['body']}, received {type(parameters['body'])}", 400

    # Create parameters variable of values to update
    parameters = {
        "message_id": parameters["message_id"],
        "body": parameters["body"],
        "updated": timezone.localtime(),
    }

    # Get the existing message object
    existing_message, code = get_message_by_id(parameters["message_id"])
    if code != 200:
        return existing_message, code  # Return error if message not found

    try:
        # Start a transaction to ensure atomicity
        with transaction.atomic():
            # Update the message fields based on valid_params
            for key, value in parameters.items():
                setattr(existing_message, key, value)

            # Save the changes to the database
            existing_message.save()
            logger.info(f"Message with ID {parameters['message_id']} updated successfully.")
            return existing_message, 200  # OK
    except Exception as e:
        logger.error(f"Error updating message with ID {parameters['message_id']}: {e}", exc_info=True)
        return "There was an internal error updating the message", 500  # Internal Server Error


# Utility function to get all messages in the database
def get_messages() -> tuple[str, int] | tuple[QuerySet, int]:
    """
    Get all messages in the database.

    returns: tuple. (QuerySet of Message objects/error message, status code).
    """
    logger.info("Attempting to retrieve all messages.")
    try:
        # Get all messages
        messages = Message.objects.all()
        for message in messages:
            # Convert datetime fields to the local time zone
            message.created = timezone.localtime(message.created)
            message.updated = timezone.localtime(message.updated)

        if not messages.exists():  # Check if the QuerySet contains any messages
            logger.info("No messages found in the database.")
            return "No messages found", 404  # Not Found

        logger.debug(f"Successfully retrieved {messages.count()} messages from the database.")
        return messages, 200  # OK

    except Exception as e:
        logger.error(f"Error retrieving messages: {e}", exc_info=True)
        return "Error retrieving messages", 500  # Internal Server Error


#  Utility function to delete an existing message 
def delete_message_by_id(message_id: int) -> tuple[str, int]:
    """
    Delete an existing message from the database by its ID.

    args: message_id (int): ID of the message to be deleted.

    returns: tuple. (Success message/error message, status code).
    """
    logger.info(f"Attempting to delete message with ID: {message_id}")
    # Get the message object (this also handles ObjectDoesNotExist)
    existing_message, code = get_message_by_id(message_id)
    if code != 200:
        return existing_message, code  # Raise error if message not found

    try:
        # Start a transaction to ensure atomicity
        with transaction.atomic():
            # Delete the message
            existing_message.delete()
            logger.info(f"Message with ID {message_id} deleted successfully.")
            return "Message deleted successfully", 200  # OK
    except Exception as e:
        logger.error(f"Error deleting message with ID {message_id}: {e}", exc_info=True)
        return "There was an internal error deleting the message", 500  # Internal Server Error


#  Utility function to get all messages from a user 
def get_messages_from_user(user_id: int) -> tuple[str, int] | tuple[QuerySet, int]:
    """
    Get all messages from a specific user.

    args: user_id (int): ID of the user whose messages are to be retrieved.

    returns: tuple. (QuerySet of Message objects/error message, status code).
    """
    logger.info(f"Attempting to retrieve messages from user with ID: {user_id}")
    # Get user by ID
    existing_user, code = get_user_by_id(user_id)
    if code != 200:
        return existing_user, code  # Return the error message and status code if user not found
    else:
        logger.debug(f"User retrieved: {existing_user}")
    try:
        # Get all messages for the user
        messages = Message.objects.filter(user=existing_user)
        for message in messages:
            # Convert datetime fields to the local time zone
            message.created = timezone.localtime(message.created)
            message.updated = timezone.localtime(message.updated)

        if not messages.exists():  # Check if the QuerySet contains any messages
            logger.info(f"No messages found for user with ID: {user_id}")
            return f"No messages found for user with ID {user_id}", 404  # Not Found

        logger.debug(f"Successfully retrieved {messages.count()} messages for user with ID: {user_id}")
        return messages, 200  # OK

    except Exception as e:
        logger.error(f"Error retrieving messages for user '{user_id}': {e}", exc_info=True)
        return f"Error retrieving messages for user '{user_id}': {e}", 500  # Internal Server Error


#  Utility function to get all messages in an activity 
def get_messages_from_activity(activity_id: int) -> tuple[str, int] | tuple[QuerySet, int]:
    """
    Get all messages within a specific activity.

    args: activity_id (int): ID of the activity whose messages are to be retrieved.

    returns: tuple. (QuerySet of Message objects/error message, status code).
    """
    logger.info(f"Attempting to retrieve messages in activity with ID: {activity_id}")
    # Get activity by ID
    existing_activity, code = get_activity_by_id(activity_id)
    if code != 200:
        return existing_activity, code  # Return the error message and status code if activity not found

    try:
        # Get all messages for the activity
        messages = Message.objects.filter(activity=existing_activity)
        for message in messages:
            # Convert datetime fields to the local time zone
            message.created = timezone.localtime(message.created)
            message.updated = timezone.localtime(message.updated)

        if code == 404:  # Check if the QuerySet contains any messages
            logger.info(f"No messages found in activity with ID: {activity_id}")
            return f"No messages found in activity with ID {activity_id} | {existing_activity}", 404  # Not Found
        if code != 200:
            logger.debug(f"Failed to retrieve messages from activity {existing_activity}")
            return f"Failed to retrieve messages from activity {existing_activity}", 500

        logger.debug(
            f"Successfully retrieved {messages.count()} messages in activity with ID: {activity_id} | {existing_activity}")
        return messages, 200  # OK

    except Exception as e:
        logger.error(f"Error retrieving messages in activity '{activity_id}': {e}", exc_info=True)
        return f"Error retrieving messages in activity '{activity_id}': {e}", 500  # Internal Server Error


def post_like_to_message(message_id: int, user_id: int) -> tuple[list | str, int]:
    """
    Post a like to a message.

    args: message_id (int): ID of the message to be liked.
          user_id (int): ID of the user who is liking the message.

    returns: tuple. (Success message/error message, status code).
    """
    logger.info(f"Attempting to like message with ID: {message_id} by user with ID: {user_id}")
    # Check if the user exists in the database
    existing_user, code = get_user_by_id(user_id)
    if code != 200:
        return existing_user, code  # Return the error message and status code if user not found

    # Get the message by ID
    existing_message, code = get_message_by_id(message_id)
    if code != 200:
        return existing_message, code  # Return the error message and status code if message not found

    try:
        # Start a transaction to ensure atomicity
        with transaction.atomic():
            # Add the user ID to the likes list of the message
            if user_id in existing_message.likes:
                return existing_message.likes, 200
            existing_message.likes.append(user_id)
            logger.info(f"User with ID {user_id} liked message with ID {message_id}.")
            return existing_message.likes, 200  # Returns the updated likes list
    except Exception as e:
        logger.error(f"Error liking message '{message_id}' by user '{user_id}': {e}", exc_info=True)
        return "There was an internal error liking the message", 500  # Internal Server Error
