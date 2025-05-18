import logging

from . import user_utils
from ..models import Client

logger = logging.getLogger(__name__)


def get_clients_by_user(user_id: int) -> tuple[list[Client], int] | tuple[str, int]:
    """
    Retrieves a list of clients associated with a specific user.

    Args:
        user_id (int): The ID of the user whose clients are to be retrieved.

    Returns:
        list: A list of Client objects associated with the user.
    """
    # Get all the clients from the database
    clients = Client.objects.all()
    # Get user object by user_id
    user, code = user_utils.get_user_by_id(user_id)
    if code != 200:
        logger.error(f"User with ID {user_id} not found.")
        return user, code  # Return an empty list if the user is not found
    # Filter the clients based on if the user_id is on the allowed_users list
    clients = [client for client in clients if user in client.allowed_users]

    return clients, 200  # Return the list of clients
