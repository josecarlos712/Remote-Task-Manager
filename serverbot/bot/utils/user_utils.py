# Get user by ID
import logging

from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


# Utility function to get a user by their ID
def get_user_by_id(user_id: int) -> tuple[str, int] | tuple[User, int]:
    """
    Get a user by their ID.

    Args:
        user_id (int): The ID of the user to retrieve.

    Returns:
        tuple: A tuple containing either the User object and status code (200) or an error message and status code (400).
    """
    # Check if the user_id is valid
    if not isinstance(user_id, int):
        return "Invalid user ID", 400

    # Check if User object already exists
    existing_user = User.objects.filter(pk=user_id).first()
    if not existing_user:
        return f"User with id {user_id} does not exist", 400

    return existing_user, 200  # OK


# Utility function to delete a user
def delete_user(user_id: int) -> tuple[str, int]:
    """
    Delete a user by their ID.

    Args:
        user_id (int): The ID of the user to delete.

    Returns:
        tuple: A tuple containing either a success message and status code (200) or an error message and status code (400).
    """
    # Check if the user_id is valid
    if not isinstance(user_id, int) or not user_id:
        return "Invalid user ID", 400

    # Check if User object exists
    existing_user = User.objects.filter(pk=user_id).first()
    if not existing_user:
        return f"User with id {user_id} does not exist", 400

    # Delete the user
    try:
        existing_user.delete()
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return "There was an internal error deleting the user", 500
    return f"User with id {user_id} deleted successfully", 200  # OK


# Utility function to update a user
def update_user(user_id: int, parameters: dict) -> tuple[str, int] | tuple[User, int]:
    """
    Update a user by their ID.

    Args:
        user_id (int): The ID of the user to update.
        parameters (dict): A dictionary containing the parameters to update.
        {
            "user_id": int,
            "username": str,
            "email": str,
            "first_name": str,
            "last_name": str,
            "password": str,
            "is_active": bool,
            "is_staff": bool,
            "is_superuser": bool,
            "groups": list,
            "email": str,
        }

    Returns:
        tuple: A tuple containing either the updated User object and status code (200) or an error message and status code (400).
    """
    # Check if the user_id is valid
    existing_user, code = get_user_by_id(user_id)
    if code != 200:
        return existing_user, code  # Raise the error message

    # Check the parameters
    expected_parameters = {
        "user_id": int,
        "username": str,
        "email": str,
        "first_name": str,
        "last_name": str,
        "password": str,
        "is_active": bool,
        "is_staff": bool,
        "is_superuser": bool,
        "groups": list,
        "user_permissions": list,
    }

    for key, value in parameters.items():
        if key not in expected_parameters:
            return f"Invalid parameter: {key}", 400
        if not isinstance(value, expected_parameters.get(key)):
            return f"Invalid type for parameter {key}: expected {expected_parameters[key]}, got {type(value)}", 400
        if value is None:
            return f"Parameter {key} cannot be None", 400

    # Check if update is necessary
    update_necessary = False
    for key, value in parameters.items():
        if key == "user_id":
            continue
        if getattr(existing_user, key) != value:
            update_necessary = True
            break

    # Update the user
    try:
        for key, value in parameters.items():
            setattr(existing_user, key, value)
        existing_user.save()
        return existing_user, 200  # OK
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return "There was an internal error updating the user", 500  # Internal Server Error


# Utility function to get the list of all users
def get_users() -> tuple[list[User] | str, int]:
    """
    Get a list of all users.

    Returns:
        tuple: A tuple containing a list of User objects or the error message and status code.
    """
    try:
        users = User.objects.all()
        return users, 200  # OK
    except Exception as e:
        logger.error(f"Error retrieving users: {e}")
        return "There was an internal error retrieving the users", 500  # Internal Server Error
