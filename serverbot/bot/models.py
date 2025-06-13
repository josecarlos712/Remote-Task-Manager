import importlib
import logging

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db import models
from django.contrib.auth.models import User
from django.db.models import TextField, ForeignKey
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings  # Import settings to reference the AUTH_USER_MODEL
from django.utils import timezone

# Loads the logger
logger = logging.getLogger(__name__)


# --- Extra util functions ---
# user.to_dict()
def user_to_dict(user: ForeignKey[User]|User) -> dict:
    return {
        'id': user.pk,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'groups': [group.name for group in user.groups.all()],  # List of group names
        'user_permissions': [perm.codename for perm in user.user_permissions.all()],  # List of permission codenames
    }


# Utility function to get a user by their ID
def get_user_by_id(user_id: int) -> tuple[str | User, int]:
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
    try:
        existing_user = User.objects.get(pk=user_id)
    except ObjectDoesNotExist:
        return f"User with id {user_id} does not exist", 400
    except MultipleObjectsReturned:
        logger.error(f"Multiple users found with id {user_id}. This should not happen.")
        return "Multiple users found with this ID, please check the database integrity.", 500
    except Exception as e:
        logger.error(f"Error retrieving user with id {user_id}: {e}")
        return "There was an internal error retrieving the user", 500

    return existing_user, 200  # OK


def time_ago(date):
    # Calculate the time difference
    now = timezone.now()  # Get the current timezone-aware time
    time_difference = now - date

    # Format the time difference into a human-readable string
    days = time_difference.days
    seconds = time_difference.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    time_ago_str_parts = []

    if days > 0:
        time_ago_str_parts.append(f"{days} {'día' if days == 1 else 'días'}")
    if hours > 0:
        time_ago_str_parts.append(f"{hours} {'hora' if hours == 1 else 'horas'}")
    if minutes > 0:
        time_ago_str_parts.append(f"{minutes} {'minuto' if minutes == 1 else 'minutos'}")
    if seconds > 0 and not time_ago_str_parts:  # Only show seconds if no larger unit is shown
        time_ago_str_parts.append(f"{seconds} {'segundo' if seconds == 1 else 'segundos'}")

    # Join the parts, or show "just now" if the difference is very small
    if time_ago_str_parts:
        # Join with "and" before the last part if there's more than one part
        if len(time_ago_str_parts) > 1:
            time_ago_str = ", ".join(time_ago_str_parts[:-1]) + " y " + time_ago_str_parts[-1]
        else:
            time_ago_str = time_ago_str_parts[0]
        time_ago_display = f"hace {time_ago_str}"
    else:
        time_ago_display = "justo ahora"  # For very recent activities
    return time_ago_display


class UserSettings(models.Model):
    """
    Stores custom settings for a user, including client API keys.
    Each user has a single UserSettings object.
    """
    # Use a OneToOneField to link directly to the User model.
    # This ensures that each User can have at most one UserSettings object.
    # on_delete=models.CASCADE means if the User is deleted, their settings are also deleted.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,  # Makes the user_id the primary key for this table
        related_name='settings',  # Allows accessing settings from the User object: user.settings
        help_text="The user associated with these settings."
    )

    # JSONField to store client API keys as a dictionary mapping client IP to API key.
    # The default=dict callable ensures a new dictionary is created for each new settings object.
    client_api_keys = models.JSONField(
        default=dict,  # Use the callable 'dict' for a mutable default (empty dictionary)
        blank=True,  # Allow the field to be blank in forms
        null=True,  # Allow the field to be null in the database (though default=dict makes this less likely needed)
        help_text="A dictionary mapping client IPs to their API keys for this user."
    )
    # The API keys are stored as a dict in a JSONField in the format:
    # {
    #  'client_name': 'API_KEY',
    # }
    # JSONField to store the user's configuration settings.
    user_config = models.JSONField(
        default=dict,  # Use the callable 'dict' for a mutable default (empty dictionary)
        blank=True,  # Allow the field to be blank in forms
        null=True,  # Allow the field to be null in the database (though default=dict makes this less likely needed)
        help_text="A dictionary for storing user-specific configuration settings."
    )

    # It refreshes the time only when its created. Then after that, it refreshes with the system time.
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Define the default ordering for Program objects.
        # Order by 'available' in descending order (-available) to show True first,
        # then by 'name' in ascending order (name) alphabetically.
        ordering = ['user']
        verbose_name = "User Settings"
        verbose_name_plural = "Users Settings"

    def to_dict(self):
        """
        Serializes the UserSettings object into a dictionary.
        """
        return {
            'user_id': self.user.pk,  # Primary key is the user ID
            'client_api_keys': self.client_api_keys if self.client_api_keys is not None else {},
            # Ensure it's a dict, even if null in DB
            'user_config': self.user_config if self.user_config is not None else {},
            # Ensure it's a dict, even if null in DB
            'updated': self.updated.isoformat() if self.updated else None,  # Format datetime
        }

    def __str__(self):
        """
        Returns a string representation of the UserSettings object.
        """
        # Access the username via the related user object
        return f"Settings for {self.user.username}"

    # You might want methods to easily manage the keys via the settings object
    def get_client_api_key(self, client_ip) -> tuple[str, int]:
        """Retrieves the API key for a specific client IP from the settings."""
        # Ensure client_api_keys is treated as a dictionary, even if null in DB
        keys_dict = self.client_api_keys if self.client_api_keys is not None else {}
        if keys_dict is None:
            logger.warning(f"No API keys found for client {client_ip}")
            return f"No API keys found for client IP: {client_ip}", 404
        return keys_dict.get(client_ip), 200

    def set_client_api_key(self, client_ip, api_key):
        """Sets or updates the API key for a specific client IP in the settings."""
        if self.client_api_keys is None:
            self.client_api_keys = {}  # Ensure it's a dictionary if it was null
        self.client_api_keys[client_ip] = api_key
        self.save()  # Remember to save the settings object after modifying the JSONField

    def remove_client_api_key(self, client_ip):
        """Removes the API key for a specific client IP from the settings."""
        if self.client_api_keys is not None and client_ip in self.client_api_keys:
            del self.client_api_keys[client_ip]
            self.save()  # Remember to save the settings object


class Client(models.Model):
    """
    Represents a remote client that can be accessed by multiple users.
    Each client has a unique local IP address and a port number.
    """
    # A field for the main user associated with this client.
    # This user is typically the owner or primary administrator of the client.
    # It's a ForeignKey to the User model.
    # Using models.SET_NULL allows the client to remain if the main user is deleted,
    # and setting null=True makes the field nullable in the database.
    main_user: ForeignKey[User] = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  # Set the main_user field to NULL when the User is deleted
        related_name='main_clients',  # Provides a reverse relation name on the User model
        null=True,  # Allow the field to be null in the database
        blank=True,  # Allow the field to be blank in forms
        help_text="The primary user associated with this client."
    )

    # Added a field for the client's name (e.g., computer name)
    # This will need to be populated by the client application sending its name to the server.
    name = models.CharField(
        max_length=255,  # Choose an appropriate max length for computer names
        null=True,  # Allow the field to be null
        blank=True,  # Allow the field to be blank in forms
        help_text="The name of the client machine (e.g., computer name)."
    )

    # A ManyToManyField to link this client to multiple allowed users.
    # We use settings.AUTH_USER_MODEL to reference the user model defined in settings.py
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='allowed_clients',  # Optional: provides a reverse relation name on the User model
        help_text="Users who are allowed to access this client."
    )

    # A field for the unique local IP address of the client.
    # unique=True ensures that no two clients have the same IP.
    local_ip = models.GenericIPAddressField(
        protocol='IPv4',  # Or 'both' if you support IPv6
        unique=True,
        null=False,
        blank=False,
        help_text="The unique local IP address of the client."
    )

    # A field for the port number used by the client application.
    port = models.IntegerField(
        null=False,
        blank=False,
        validators=[
            MinValueValidator(1024),
            MaxValueValidator(65535)
        ],
        help_text="The port number the client application is listening on."
    )

    def to_dict(self):
        """
        Serializes the Client object into a dictionary.
        """
        # Get IDs and usernames for related fields, handling nulls
        main_user_id = self.main_user.pk if self.main_user else None
        main_user_username = self.main_user.username if self.main_user else None

        # Get IDs and usernames for ManyToManyField (allowed_users)
        # This will be a list of dictionaries, each with user ID and username
        allowed_users_list = []
        for user in self.allowed_users.all():  # Iterate through the related users
            allowed_users_list.append({
                'id': user.pk,
                'username': user.username
            })

        return {
            'id': self.pk,  # Primary key
            'main_user_id': main_user_id,
            'main_user_username': main_user_username,
            'name': self.name,
            'local_ip': self.local_ip,
            'port': self.port,
            'allowed_users': allowed_users_list,  # Include the list of allowed users
            # Add other fields here if needed
        }

    def __str__(self):
        """
        Returns a string representation of the Client object.
        """
        return f"{self.main_user.username} at {self.local_ip}:{self.port}"

    class Meta:
        # '-updated' for inverse ordering, and 'updated' for normal ordering
        ordering = ['local_ip', 'main_user']

    def is_user_allowed(self, user) -> tuple[str, int]:
        """
        Checks if a given user is in the list of allowed users for this client.

        Args:
            user (int): The user to check against the allowed users for this client.

        Returns:
            tuple (str, int): Returns a tuple containing the client object or a error message and a boolean indicating success.
        """
        if isinstance(user, User):
            user_id = user.pk  # Get the primary key of the User object
        elif isinstance(user, int):
            user_id = user  # Assume user is an ID
        else:
            logger.error(f"Invalid user type: {type(user)}. Expected User object or user ID.")
            return "Invalid user type. Expected User object or user ID.", 400

        # Client owner is always allowed
        print(f"Client owner: {self.main_user.pk}")
        if self.main_user.pk == user_id:
            logger.debug(f"User {user_id} is the main user for client {self}.")
            return "User is the main user for this client.", 200

        allowed = self.allowed_users.filter(pk=user_id).exists()
        if allowed:
            logger.debug(f"User {user} is allowed for client {self}.")
            return "User is allowed for this client.", 200
        else:
            logger.debug(f"User {user} is NOT allowed for client {self}.")
            return "User is NOT allowed for this client.", 403  # Forbidden


class Activity(models.Model):
    title = models.TextField(null=True, blank=True)
    name = models.TextField(null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        """
        Returns a string representation of the Activity object.
        """
        user_str = self.user.username if self.user else "[Anonymous]"
        # Format the time difference for display
        time_ago_display = time_ago(self.created)
        # Construct the final string
        return f"Activity: {self.name} by {user_str} ({time_ago_display})"

    class Meta:
        # Define the default ordering for Program objects.
        # Order by 'available' in descending order (-available) to show True first,
        # then by 'name' in ascending order (name) alphabetically.
        ordering = ['name']
        verbose_name = "Activity"
        verbose_name_plural = "Activities"

    def to_dict(self):
        """
        Serializes the Activity object into a dictionary.
        This dictionary is suitable for JSON responses.
        """
        # Get the user object and get its dict
        user_name = self.user.username if self.user else None
        return {
            'id': self.pk,  # Include the primary key
            'name': self.name,
            'title': self.title,
            'description': self.description,
            'user_name': user_name,
            'number_of_messages': Message.objects.filter(activity=self).count(),  # Count messages related to this activity
            # Format datetime fields to ISO 8601 strings for JSON
            'created': self.created.isoformat() if self.created else None,
            'updated': self.updated.isoformat() if self.updated else None,
            # Add other fields here if needed
        }


class Message(models.Model):  # One message can have only one activity and user
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=False)
    # CASCADE deletes all messages if the activity is deleted
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, null=True, blank=False)
    body = models.TextField(blank=True, default="")
    # Likes is a list of users who liked the message. It stores the user ID.
    likes = models.JSONField(
        default=list,  # Use the callable 'list' for a mutable default (empty list)
        blank=True,  # Allow the field to be blank in forms
        null=True,  # Allow the field to be null in the database (though default=list makes this less likely needed)
        help_text="A list of user IDs who liked this message."
    )
    # It refreshes with the system time
    updated = models.DateTimeField(default=timezone.now)
    # It refreshes the time only when its created
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        # '-updated' for inverse ordering, and 'updated' for normal ordering
        ordering = ['-updated', '-created']

    def to_dict(self):
        """
        Serializes the Message object into a dictionary.
        """
        # Get IDs and usernames for related fields, handling nulls
        user_id = self.user.pk if self.user else None
        user_username = self.user.username if self.user else None
        activity_id = self.activity.pk if self.activity else None
        activity_name = self.activity.name if self.activity else None

        like_users = []
        for user_id in self.likes:
            user, code = get_user_by_id(user_id)  # Get user object by ID
            if code == 200:
                like_users.append(user.username)

        # room_id = self.room.pk if hasattr(self, 'room') and self.room else None # If Room FK exists
        # room_name = self.room.name if hasattr(self, 'room') and self.room else None # If Room FK exists

        return {
            'id': self.pk,  # Primary key
            'user_id': user_id,
            'user_username': user_username,
            'activity_id': activity_id,
            'activity_name': activity_name,
            'body': self.body,
            'likes': like_users,  # List of user IDs who liked the message
            'updated': self.updated.isoformat() if self.updated else None,  # Format datetime
            'created': self.created.isoformat() if self.created else None,  # Format datetime
        }

    def __str__(self):
        """
        Returns a string representation of the Message object.
        """
        user_str = self.user.username if self.user else "Unknown User"
        # Truncate message body for a concise representation
        body_snippet = self.body[:50] + '...' if len(self.body) > 50 else self.body
        # Include activity name if available
        activity_name = self.activity.name if self.activity else "Unknown Activity"
        return f"Message by {user_str} in '{activity_name}': \"{body_snippet[:20]}\" on {self.created.strftime('%Y-%m-%d %H:%M:%S')}"


class Program(models.Model):
    """
        Represents a program that can be managed or executed on a client.
        Uses an integer program_id as the primary key.
        """
    # Program identifier, now an integer primary key.
    # This ID should uniquely identify the program definition across the system,
    # or at least within a client if programs are client-specific.
    # Program's internal name (not the primary key anymore)
    name = models.TextField(
        null=False,
        blank=False,
        help_text="The internal name or identifier for the program. No spaces or special characters. Only [a-zA-Z0-9_]."
    )

    title = models.TextField(
        null=False,
        blank=False,
        default="Untitled program",
        help_text="The display title for the program."
    )

    description = models.CharField(
        max_length=200,
        null=True,  # Allow null description
        default="None",  # Default value if null is allowed
        help_text="A brief description of the program."
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='programs',  # Provides a reverse relation name on the Client model
        null=True,  # Allow null client (as per previous discussion)
        blank=False,
        help_text="The client this program is associated with."
    )

    available = models.BooleanField(
        default=False,
        help_text="Indicates if the program is currently available for execution."
    )

    # hidden fields (as per your comment) - not typically hidden in the model definition itself,
    # but might be excluded from forms or admin views.
    is_running = models.BooleanField(
        default=False,
        help_text="Indicates if the program is currently running."
    )

    start_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The timestamp when the program was started."
    )

    end_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The timestamp when the program finished."
    )

    # It refreshes the time only when its created. Then after that, it refreshes with the system time.
    updated = models.DateTimeField(default=timezone.now)
    # It refreshes the time only when its created
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        # Define the default ordering for Program objects.
        # Order by 'available' in descending order (-available) to show True first,
        # then by 'name' in ascending order (name) alphabetically.
        ordering = ['-available', 'name']
        verbose_name = "Program"
        verbose_name_plural = "Programs"

    def to_dict(self):
        """
        Serializes the Program object into a dictionary.
        """
        # Get client ID and string representation, handling null
        client_id = self.client.pk if self.client else None
        client_str = str(self.client) if self.client else None

        return {
            'id': self.pk,  # Primary key
            'name': self.name,
            'title': self.title,
            'description': self.description,
            'client_id': client_id,  # Include client ID
            'client_info': client_str,  # Include client string representation (optional)
            'available': self.available,
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,  # Format datetime
            'end_time': self.end_time.isoformat() if self.end_time else None,  # Format datetime
            'updated': self.updated.isoformat() if self.updated else None,  # Format datetime
            'created': self.created.isoformat() if self.created else None,  # Format datetime
            # Add other fields here if needed
        }

    def is_equal(self, comparator):
        """
        Compares this Program instance to a dictionary representation.
        Used for synchronization logic, comparing definition details.
        """
        # Ensure comparator is a dictionary
        if not isinstance(comparator, dict):
            return False

        # Compare relevant fields for equality based on the dictionary structure
        # Use .get() with a default for comparator fields to avoid KeyError
        # Compare name case-insensitively as in your original code
        # Note: program_id is the database PK, but comparison for sync might be based on name/title/description
        return (
                str(self.name).lower() == str(comparator.get('name', '')).lower()
                and self.title == comparator.get('title', '')
                and self.description == comparator.get('description', 'None')
                and self.program_id == comparator.get('program_id')
            # Note: available, is_running, timestamps are typically not used for equality comparison because they are volatile data.
            # If the program_id is also expected in the comparator dict and should be compared:
            # and self.program_id == comparator.get('program_id') # Add this line if program_id is in sync source
        )

    def __str__(self):
        """
        Returns a string representation of the Program object.
        Includes the program_id for clarity.
        """
        status = "Running" if self.is_running else ("Available" if self.available else "Unavailable")
        # Updated __str__ to include the program_id
        return f"Program: {self.title} ({self.name}) [ID: {self.program_id}] - Status: {status}"

    def __eq__(self, program):
        """
        Compares this Program instance with another object.
        This is a custom equality check for Program instances.
        """
        if program.name != self.name:
            return False
        if program.title != self.title:
            return False
        # Update description only if there's new info
        if program.description is not None and program.description != self.description:
            return False
        # Update available only if there's new info
        if program.available is not None and self.available != program.available:
            return False
        return True

    @staticmethod
    def get_program_by_ID(program_id):
        """
        Retrieves a Program instance by its ID.

        Args:
            program_id (int): The Program ID representing the Program sending the program list.

        Returns:
            tuple (String/Program, int): Returns a tuple containing the Program object or an error message and a boolean indicating success.
        """
        try:
            program_obj = Program.objects.get(pk=program_id)
            logger.debug(f"api_update_program_list() - Successfully retrieved program: {program_obj}")
            return program_obj, True

        except ObjectDoesNotExist:
            logger.warning(f"api_update_program_list() - Program with ID '{program_id}' not found.")
            return f"api_update_program_list() - Program with ID '{program_id}' not found.", False

        except MultipleObjectsReturned:
            logger.error(f"api_update_program_list() - Multiple Programs found for ID '{program_id}'. Database error?")
            return f"api_update_program_list() - Multiple programs found for ID '{program_id}'. Database error?", False

        except Exception as e:
            logger.error(f"api_update_program_list() - Error retrieving program '{program_id}': {e}", exc_info=True)
            return f"api_update_program_list() - Error retrieving program '{program_id}': {e}", False


class Command(models.Model):
    """
    Represents a command that can be executed on a specific client.
    Each command is linked to a Client and has a unique command_id within that client.
    The actual command execution logic resides on the client application.
    """
    # Django automatically adds an 'id' field as the primary key (BigAutoField).
    # This is the autogenerated incremental private key.

    # ForeignKey to the Client model.
    # on_delete=models.CASCADE means if a Client is deleted, all its Commands are also deleted.
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='commands',  # Provides a reverse relation name on the Client model (e.g., client.commands.all())
        null=True,  # Allow null client (as per previous discussion)
        blank=False,
        help_text="The client this command belongs to."
    )

    name = models.TextField(null=False, blank=False)
    title = models.TextField(null=False, blank=False, default="Untitled command")
    description = models.TextField(null=False, blank=True, default="")

    # JSONField is suitable for storing the list of expected argument types.
    # The default=list callable ensures a new empty list is created for each new command.
    args = models.JSONField(null=True, blank=True, default=list)

    # It refreshes the time only when its created. Then after that, it refreshes with the system time.
    updated = models.DateTimeField(default=timezone.now)
    # It refreshes the time only when its created
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        # Enforce uniqueness of command_id for a given client.
        # This prevents two commands for the same client having the same command_id.
        constraints = [
            models.UniqueConstraint(fields=['client', 'name'], name='unique_command_per_client')
        ]
        # Define default ordering for commands (e.g., by client and then command_id)
        ordering = ['client__local_ip', 'client__port', 'name']
        verbose_name = "Command"
        verbose_name_plural = "Commands"

    def to_dict(self):
        """
        Serializes the Command object into a dictionary.
        """
        # Get client ID and string representation, handling null
        self.client: Client
        client_id = self.client.pk if self.client else None
        client_str = str(self.client) if self.client else None

        return {
            'id': self.pk,  # Primary key
            'command_id': self.pk,
            'name': self.name,
            'title': self.title,
            'description': self.description,
            'client_id': client_id,  # Include client ID
            'client_info': client_str,  # Include client string representation (optional)
            'args': self.args if self.args is not None else [],  # Ensure args is a list, even if null
            'updated': self.updated.isoformat() if self.updated else None,  # Format datetime
            'created': self.created.isoformat() if self.created else None,  # Format datetime
            # Note: Handler is typically not included in the public API response,
            # as it's server-side execution logic. Include if necessary.
            # 'handler': self.handler,
            # Add other fields here if needed
        }

    def __str__(self):
        """
        Returns a string representation of the Command object.
        """
        # Updated __str__ to remove handler
        client_str = str(self.client) if self.client else "No Client"
        return f"Command: {self.name} on {client_str}"
