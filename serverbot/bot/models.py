import importlib
import logging

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db import models
from django.contrib.auth.models import User
from django.db.models import TextField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings  # Import settings to reference the AUTH_USER_MODEL
from django.utils import timezone


# Loads the logger
logger = logging.getLogger(__name__)


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

    # It refreshes the time only when its created. Then after that, it refreshes with the system time.
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Define the default ordering for Program objects.
        # Order by 'available' in descending order (-available) to show True first,
        # then by 'name' in ascending order (name) alphabetically.
        ordering = ['user']
        verbose_name = "User Settings"
        verbose_name_plural = "Users Settings"

    def __str__(self):
        """
        Returns a string representation of the UserSettings object.
        """
        # Access the username via the related user object
        return f"Settings for {self.user.username}"

    # You might want methods to easily manage the keys via the settings object
    def get_client_api_key(self, client_ip):
        """Retrieves the API key for a specific client IP from the settings."""
        # Ensure client_api_keys is treated as a dictionary, even if null in DB
        keys_dict = self.client_api_keys if self.client_api_keys is not None else {}
        return keys_dict.get(client_ip)

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
    main_user = models.ForeignKey(
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

    def __str__(self):
        """
        Returns a string representation of the Client object.
        """
        return f"Client {self.main_user.username} at {self.local_ip}:{self.port}"

    class Meta:
        # '-updated' for inverse ordering, and 'updated' for normal ordering
        ordering = ['local_ip', 'main_user']

    def is_user_allowed(self, user):
        """
        Checks if a given user is in the list of allowed users for this client.

        Args:
            user (User): The user to check against the allowed users for this client.

        Returns:
            tuple (String/Client, int): Returns a tuple containing the client object or a error message and a boolean indicating success.
        """
        allowed = self.allowed_users.filter(pk=user.pk).exists()
        if allowed:
            logger.debug(f"User {user.username} is allowed for client {self.local_ip}.")
            return "User is allowed for client.", True
        else:
            logger.debug(f"User {user.username} is NOT allowed for client {self.local_ip}.")
            return "User is NOT allowed for client.", False

    @staticmethod
    def get_client_by_ID(client_id):
        """
        Retrieves a client instance by its ID.

        Args:
            client_id (int): The Client ID representing the client sending the program list.

        Returns:
            tuple (String/Client, int): Returns a tuple containing the client object or a error message and a boolean indicating success.
        """
        try:
            client_obj = Client.objects.get(pk=client_id)
            logger.debug(f"api_update_program_list() - Successfully retrieved client: {client_obj}")
            return client_obj, True

        except ObjectDoesNotExist:
            logger.warning(f"api_update_program_list() - Client with ID '{client_id}' not found.")
            return f"api_update_program_list() - Client with ID '{client_id}' not found.", False

        except MultipleObjectsReturned:
            logger.error(f"api_update_program_list() - Multiple clients found for ID '{client_id}'. Database error?")
            return f"api_update_program_list() - Multiple clients found for ID '{client_id}'. Database error?", False

        except Exception as e:
            logger.error(f"api_update_program_list() - Error retrieving client '{client_id}': {e}", exc_info=True)
            return f"api_update_program_list() - Error retrieving client '{client_id}': {e}", False


class Activity(models.Model):
    name = models.TextField(null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(default=timezone.now)
    hour = models.TimeField(default=timezone.now)

    def __str__(self):
        """
        Returns a string representation of the Activity object.
        """
        user_str = self.user.username if self.user else "Anonymous"
        # Format date and time for better readability
        formatted_date = self.date.strftime("%Y-%m-%d")
        formatted_time = self.hour.strftime("%H:%M")
        return f"Activity: {self.name} by {user_str} on {formatted_date} at {formatted_time}"

    class Meta:
        # Define the default ordering for Program objects.
        # Order by 'available' in descending order (-available) to show True first,
        # then by 'name' in ascending order (name) alphabetically.
        ordering = ['name']
        verbose_name = "Activity"
        verbose_name_plural = "Activities"


class Message(models.Model):  # One message can have only one activity and user
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=False)
    # CASCADE deletes all messages if the activity is deleted
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, null=True, blank=False)
    body = models.TextField(blank=True, default="")
    # It refreshes with the system time
    updated = models.DateTimeField(default=timezone.now)
    # It refreshes the time only when its created
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        # '-updated' for inverse ordering, and 'updated' for normal ordering
        ordering = ['-updated', '-created']

    def __str__(self):
        """
        Returns a string representation of the Message object.
        """
        user_str = self.user.username if self.user else "Unknown User"
        # Truncate message body for a concise representation
        body_snippet = self.body[:50] + '...' if len(self.body) > 50 else self.body
        # Include activity name if available
        activity_name = self.activity.name if self.activity else "Unknown Activity"
        return f"Message by {user_str} in '{activity_name}': \"{body_snippet}\""


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

    def __str__(self):
        """
        Returns a string representation of the Command object.
        """
        # Updated __str__ to remove handler
        client_str = str(self.client) if self.client else "No Client"
        return f"Command: {self.name} on {client_str}"

    @staticmethod
    def get_command_by_id(command_id: str):
        """
        Retrieves a Command object from the database based on its command_id.

        Args:
            command_id (str): The unique identifier of the command to retrieve.

        Returns:
            Command or None: The Command object if found, None otherwise.
        """
        if not isinstance(command_id, str):
            return "get_command_by_id() - command_id is not a string.", False
        if command_id is None:
            return "get_command_by_id() - Received None command_id.", False

        try:
            # Get the Command object by its command_id
            command: Command = Command.objects.get(command_id=command_id)
            return command  # Return the found command object

        except ObjectDoesNotExist:
            # Handle the case where a Command with the given command_id does not exist
            logger.warning(f"Command with ID '{command_id}' not found in the database.")
            return None  # Indicate that the command was not found
