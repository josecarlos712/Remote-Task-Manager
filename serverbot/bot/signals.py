# your_app/signals.py
# TODO: Replace 'your_app' with the actual name of your Django app

from django.db.models.signals import post_save # Import the post_save signal
from django.contrib.auth import get_user_model # Recommended way to get the User model
from django.dispatch import receiver # Import the receiver decorator
from .models import UserSettings # Import your UserSettings model (assuming it's in models.py in the same app)
import logging

logger = logging.getLogger(__name__)

# Get the User model
User = get_user_model()


# Use the @receiver decorator to connect this function to the post_save signal
# sent by the User model.
@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    """
    Signal receiver function to create a UserSettings object
    automatically when a new User is created.
    """
    # 'instance' is the User object that was just saved
    # 'created' is a boolean indicating if the User was just created
    #logger.debug(f"Signal received for user '{instance.username}'. Created: {created}")

    if created:
        # This block runs ONLY when a new User object is created and saved for the first time.
        logger.debug(f"User '{instance.username}' was created. Attempting to create UserSettings.")
        try:
            # Create a new UserSettings object and link it to the new User
            UserSettings.objects.create(user=instance)
            logger.debug(f"UserSettings created successfully for user '{instance.username}'.")
        except Exception as e:
            logger.error(f"Error creating UserSettings for user '{instance.username}': {e}", exc_info=True)
            raise
            # TODO: Decide how to handle this error. It might be critical if settings are essential.
