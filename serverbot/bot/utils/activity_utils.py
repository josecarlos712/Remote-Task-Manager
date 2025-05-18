# Crear actividad (user_id, parametros)
import logging
from datetime import datetime
from typing import Tuple, Any

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from ..models import Activity
from .user_utils import get_user_by_id


logger = logging.getLogger(__name__)


# Utility function to create an activity in the database
def create_activity(parameters) -> tuple[str, int] | tuple[Activity, int]:
    """
    Create an activity in the database.

    args: parameters (dict): Parameters for the activity.
    {
        "user_id": int,
        "title": str,
        "name": str,
        "description": str,
    }

    returns: tuple. (Activity object/error message, status code).
    """
    # Date and hour of the activity is automatically set by the database.
    # Check the parameters dictionary for the required keys
    expected_types = {
        "user_id": int,
        "title": str,
        "name": str,
        "description": str,
    }
    # Check if the dictionary contains the expected keys and types
    for key, expected_type in expected_types.items():
        if key not in parameters:
            return f"Missing parameter: {key}", 400
        if not isinstance(parameters[key], expected_type):
            return f"Invalid type for parameter {key}: expected {expected_type}, got {type(parameters[key])}", 400

    # Check if the user exists in the database
    user_id = parameters["user_id"]
    existing_user, code = get_user_by_id(user_id)
    if code != 200:
        return existing_user, code  # Raise the error message and status code if user not found

    try:
        # Start a transaction to ensure atomicity
        with transaction.atomic():
            # Create the activity
            activity, created = Activity.objects.get_or_create(
                user=existing_user,
                name=parameters["name"],
                title=parameters["title"],
                description=parameters["description"],
            )
            # Convert datetime fields to the local time zone
            activity.created = timezone.localtime(activity.created)
            activity.updated = timezone.localtime(activity.updated)
            if not created:
                return "Activity already exists", 400  # Bad Request

            return activity, 201  # Created
    except Exception as e:
        logger.error(f"Error creating activity: {e}")
        return "There was an internal error creating the activity", 500  # Internal Server Error


# Utility function to get an existing activity
def get_activity_by_id(activity_id: int) -> tuple[str, int] | tuple[Activity, int]:
    """
    Get an existing activity from the database.

    args: activity_id (int): ID of the activity to be retrieved.

    returns: tuple. (Activity object/error message, status code).
    """
    # Check if the activity_id is valid
    if not isinstance(activity_id, int):
        return "Invalid activity ID", 400

    # Check if Activity object exists
    try:
        # Get the Activity object by its primary key (pk)
        existing_activity = Activity.objects.get(pk=activity_id)
        # Convert datetime fields to the local time zone
        existing_activity.created = timezone.localtime(existing_activity.created)
        existing_activity.updated = timezone.localtime(existing_activity.updated)
        logger.debug(f"Activity retrieved successfully with ID: {activity_id}")
        return existing_activity, 200  # OK

    except ObjectDoesNotExist:
        logger.warning(f"Activity with ID '{activity_id}' does not exist.")
        return f"Activity with id {activity_id} does not exist", 404  # Not Found

    except MultipleObjectsReturned:
        # Should not happen for primary key lookup, but included for robustness
        logger.error(f"Multiple activitys found for ID '{activity_id}'. Database error?")
        return f"Multiple activitys found for ID '{activity_id}'. Database error?", 500  # Internal Server Error

    except Exception as e:
        logger.error(f"Error retrieving activity '{activity_id}': {e}", exc_info=True)
        return f"Error retrieving activity '{activity_id}': {e}", 500  # Internal Server Error


# Utility function to update an existing activity
def update_activity(activity_id, parameters) -> tuple[str, int] | tuple[Activity, int]:
    """
    Update an existing activity in the database.

    args: activity_id (int): ID of the activity to be updated.
          parameters (dict): Parameters for the activity.
    {
        "name": str,
        "description": str,
    }
    returns: tuple. (Activity object/error message, status code).
    """
    existing_activity, code = get_activity_by_id(activity_id)

    # Check if the parameters dictionary contains the expected keys and types
    expected_types = {
        "user_id": int,
        "title": str,
        "name": str,
        "description": str,
    }
    for key, expected_type in expected_types.items():
        if key in parameters and not isinstance(parameters[key], expected_type) and parameters[key]:
            return f"Invalid type for parameter {key}: expected {expected_type}, got {type(parameters[key])}", 400

    # Check if an update is necessary
    update_necessary = False
    for key, _ in expected_types.items():
        existing_activity_value = getattr(existing_activity, key)
        if key in parameters and existing_activity_value != parameters[key]:
            if not update_necessary:
                update_necessary = True
                break

    if not update_necessary:
        return "No updates necessary", 200

    try:
        # Start a transaction to ensure atomicity
        with transaction.atomic():
            # Update the activity
            for key, value in parameters.items():
                setattr(existing_activity, key, value)
            # Update the 'update' field to current date and time
            existing_activity.update = datetime.now()
            # Save the changes to the database
            existing_activity.save()
            return existing_activity, 200  # OK
    except Exception as e:
        logger.error(f"Error updating activity: {e}")
        return "There was an internal error updating the activity", 500  # Internal Server Error


# Utility function to delete an existing activity
def delete_activity(activity_id) -> tuple[str, int]:
    """
    Delete an existing activity from the database.

    args: activity_id (int): ID of the activity to be deleted.

    returns: tuple. (Activity object/error message, status code).
    """
    # Get the activity object
    existing_activity, code = get_activity_by_id(activity_id)
    if code != 200:
        return existing_activity, code  # Raise the error message and status code if activity not found

    try:
        # Start a transaction to ensure atomicity
        with transaction.atomic():
            # Delete the activity
            existing_activity.delete()
            return "Activity deleted successfully", 200  # OK
    except Exception as e:
        logger.error(f"Error deleting activity: {e}")
        return "There was an internal error deleting the activity", 500  # Internal Server Error


# Utility function to get all activities
def get_activities() -> tuple[str, int] | tuple[QuerySet, int]:
    """
    Get all activities from the database.

    returns: tuple. (QuerySet/error message, status code).
    """
    # Get all activities
    activities = Activity.objects.all()
    for activity in activities:
        # Convert datetime fields to the local time zone
        activity.created = timezone.localtime(activity.created)
        activity.updated = timezone.localtime(activity.updated)

    if not activities:
        return "No activities found", 404  # Not Found

    return activities, 200  # OK


# Utility function to get all activities for a user
def get_activities_from_user(user_id: int) -> tuple[str, int] | tuple[QuerySet, int]:
    """
    Get all activities for a user.

    args: user_id (int): ID of the user whose activities are to be retrieved.

    returns: tuple. (Activity object/error message, status code).
    """
    # Get user by ID
    existing_user, code = get_user_by_id(user_id)

    if code != 200:
        return existing_user, code  # Raise the error message and status code if user not found

    # Get all activities for the user
    activities = Activity.objects.filter(user=existing_user)
    for activity in activities:
        # Convert datetime fields to the local time zone
        activity.created = timezone.localtime(activity.created)
        activity.updated = timezone.localtime(activity.updated)

    if not activities:
        return f"No activities found for user {user_id}", 404  # Not Found

    return activities, 200   # OK
