import importlib
import logging

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
        primary_key=True, # Makes the user_id the primary key for this table
        related_name='settings', # Allows accessing settings from the User object: user.settings
        help_text="The user associated with these settings."
    )

    # JSONField to store client API keys as a dictionary mapping client IP to API key.
    # The default=dict callable ensures a new dictionary is created for each new settings object.
    client_api_keys = models.JSONField(
        default=dict, # Use the callable 'dict' for a mutable default (empty dictionary)
        blank=True,   # Allow the field to be blank in forms
        null=True,    # Allow the field to be null in the database (though default=dict makes this less likely needed)
        help_text="A dictionary mapping client IPs to their API keys for this user."
    )

    # TODO: Add other user-specific settings fields here as needed

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
            self.client_api_keys = {} # Ensure it's a dictionary if it was null
        self.client_api_keys[client_ip] = api_key
        self.save() # Remember to save the settings object after modifying the JSONField

    def remove_client_api_key(self, client_ip):
        """Removes the API key for a specific client IP from the settings."""
        if self.client_api_keys is not None and client_ip in self.client_api_keys:
            del self.client_api_keys[client_ip]
            self.save() # Remember to save the settings object


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
        """
        return self.allowed_users.filter(pk=user.pk).exists()


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


class Program(models.Model):
    name = models.TextField(null=False, blank=False)
    title = models.TextField(null=False, blank=False,
                             default="Untitled program")
    path = models.TextField(null=False, blank=True, unique=True)
    command = models.TextField(null=True, default="None")
    description = models.CharField(max_length=200, null=True, default="None")
    available = models.BooleanField(default=False)
    # activity = models.ForeignKey(Activity, on_delete=models.DO_NOTHING, null=False)
    # hidden fields
    id = models.BigAutoField(primary_key=True)  # ID único y autoincremental
    is_running = models.BooleanField(default=False)

    def is_equal(self, comparator):
        return str(self.name).lower() == str(comparator['name']).lower() and self.title == comparator[
            'title'] and self.path == comparator['path'] and self.command == comparator.get('command',
                                                                                            'None') and self.description == comparator.get(
            'description', 'None')

    def __str__(self):
        """
        Returns a string representation of the Program object.
        """
        return f"Program: {self.title} ({self.name})"


class Command(models.Model):
    # ForeignKey to the Client model.
    # on_delete=models.CASCADE means if a Client is deleted, all its Commands are also deleted.
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='commands',  # Provides a reverse relation name on the Client model (e.g., client.commands.all())
        null=True,  # A command must belong to a client
        blank=False,
        help_text="The client this command belongs to."
    )

    # command_id is unique per client, not globally.
    command_id = models.TextField(null=False, blank=False)
    name = models.TextField(null=False, blank=False)
    description = models.TextField(null=False, blank=True, default="")
    # Storing handler in the DB is fine, but ensure it's the import path (e.g., 'commands.hello_world.handler')
    handler = models.TextField(null=False, blank=False, default="")  # handler is used by the execution logic
    # JSONField is suitable for storing the list of args
    args = models.JSONField(null=True, blank=True, default=list)

    class Meta:
        # Enforce uniqueness of command_id for a given client.
        # This prevents two commands for the same client having the same command_id.
        constraints = [
            models.UniqueConstraint(fields=['client', 'command_id'], name='unique_command_per_client')
        ]
        # Define default ordering for commands (e.g., by client and then command_id)
        ordering = ['client__local_ip', 'client__port', 'command_id']
        verbose_name = "Command"
        verbose_name_plural = "Commands"

    def __str__(self):
        """
        Returns a string representation of the Command object.
        """
        return f"Command: {self.name} ({self.command_id}): {self.handler}({self.args})"  # More descriptive string

    def __eq__(self, other):
        """
        Compares two Command objects for equality.
        Two commands are considered equal if their command_id, name, description,
        handler, and args are the same.
        """
        if not isinstance(other, Command):
            # Not comparing with a Command instance, so they are not equal
            return False

        # Compare relevant fields for equality
        return (
                self.command_id == other.command_id and
                self.name == other.name and
                # self.description == other.description and  # Description is not relevant for equality
                self.handler == other.handler and
                self.args == other.args  # JSONField comparison handles list equality
        )

    def __hash__(self):
        """
        Returns a hash value for the Command object.
        Required when implementing __eq__ and using objects in sets or as dictionary keys.
        """
        # Use a tuple of the fields to generate the hash
        return hash((self.command_id, self.name, self.description, self.handler,
                     tuple(self.args if self.args is not None else [])))

    def to_dict(self):
        """
        Returns a dictionary representation of the Command object,
        matching the structure of the commands.json entries.
        """
        return {
            self.command_id: {
                "name": self.name,
                "description": self.description,
                "args": self.args if self.args is not None else [],
                "handler": self.handler
            }
        }

    # You might also want a method to get the details *without* the command_id as the key
    def get_details_dict(self):
        """
        Returns a dictionary of command details without the command_id as the key.
        Useful when listing commands.
        """
        return {
            "command_id": self.command_id,
            "name": self.name,
            "description": self.description,
            "args": self.args if self.args is not None else [],
            "handler": self.handler
        }

    def check_args(self, args):
        """
        Validates the provided arguments against the expected argument types.
        Raises TypeError if the argument types do not match.

        Args:
            args (list): List of arguments to validate.

        Raises:
            TypeError: If the argument types do not match the expected types.
        """
        # Type Validation for Positional Arguments
        expected_args_types = self.args if self.args is not None else []
        if len(args) != len(expected_args_types):
            error_message = f"Command '{self.command_id}' expects {len(expected_args_types)} positional arguments, but {len(args)} were provided."
            logger.error(error_message)
            raise TypeError(error_message)  # Raise TypeError for incorrect argument count
        # Validate argument types
        for i, (arg, expected_type) in enumerate(zip(args, expected_args_types)):
            if not isinstance(arg, expected_type):
                error_message = f"{self.command_id} expected the positional arguments ({expected_args_types}) but got ({args}) instead."
                logger.error(error_message)
                raise TypeError(error_message)

    # Execute the command handler with the provided arguments
    def __call__(self, *args, **kwargs):
        """
        Makes the Command instance callable.
        Dynamically imports the module specified by the 'handler' field
        and executes the function (assumed to be named 'handler') within it.

        Args:
            *args: Positional arguments to pass to the command handler function.
            **kwargs: Keyword arguments to pass to the command handler function.

        Returns:
            dict: The result returned by the command handler function.
                  Should ideally include 'status' or 'success' and 'message'.

        Raises:
            ImportError: If the module specified in 'handler' cannot be imported.
            AttributeError: If the 'handler' function is not found within the imported module.
            TypeError: If the handler function is called with incorrect arguments.
            Exception: If an error occurs during the execution of the command handler.
        """
        if not self.handler:
            logger.error(f"Command '{self.command_id}' has no handler defined.")
            # Return an error response if no handler is specified
            return {'status': 'error', 'message': f"No handler defined for command '{self.command_id}'."}

        # Split the handler path into module path and function name
        try:
            # Assuming handler is in the format 'module.submodule.function_name'
            module_path, function_name = self.handler.rsplit('.', 1)
        except ValueError:
            logger.error(
                f"Invalid handler format for command '{self.command_id}': '{self.handler}'. Expected 'module.function_name'.")
            return {'status': 'error', 'message': f"Invalid handler format for command '{self.command_id}'."}

        # Dynamically import the module
        logger.debug(f"Attempting to import module: {module_path}")
        try:
            module = importlib.import_module(module_path)
            logger.debug(f"Successfully imported module: {module_path}")
        except ImportError as e:
            logger.error(f"Could not import module '{module_path}' for command '{self.command_id}': {e}", exc_info=True)
            # Re-raise the exception or return an error response
            # Raising might be better for critical import failures during execution
            # raise ImportError(f"Could not import module '{module_path}'") from e
            return {'status': 'error', 'message': f"Could not find command module: {module_path}"}

        # Get the function from the module
        logger.debug(f"Attempting to get function '{function_name}' from module '{module_path}'")
        try:
            handler_function = getattr(module, function_name)
            logger.debug(f"Successfully got function '{function_name}'")
        except AttributeError as e:
            logger.error(
                f"Could not find function '{function_name}' in module '{module_path}' for command '{self.command_id}': {e}",
                exc_info=True)
            # Re-raise or return error response
            # raise AttributeError(f"Could not find function '{function_name}' in module '{module_path}'") from e
            return {'status': 'error', 'message': f"Could not find handler function: {function_name}"}

        # Check args
        self.check_args(args)

        # Execute the handler function, passing any arguments
        logger.debug(f"Executing handler function '{function_name}' with args: {args}, kwargs: {kwargs}")
        try:
            # The handler blueprint expects *args and **kwargs
            result = handler_function(*args, **kwargs)
            logger.debug(f"Handler function '{function_name}' executed. Result: {result}")
            return result  # Return the result from the handler
        except Exception as e:
            logger.error(f"Error executing handler function '{function_name}' for command '{self.command_id}': {e}",
                         exc_info=True)
            # Catch any exceptions during execution and return an error response
            # TODO: Decide if you want to expose the raw exception message or a generic error
            return {'status': 'error', 'message': f"Error during command execution: {str(e)}"}


class Room(models.Model):  # One room can have multiple messages
    host = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=200)
    # It can be blank because null=True
    description = models.TextField(null=True, blank=True)
    # this creates a many-to-many relationship in the database
    participants = models.ManyToManyField(
        User, related_name='participants', blank=True)
    # It refreshes with the system time
    updated = models.DateTimeField(auto_now=True)
    # It refreshes the time only when its created
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        # '-updated' for inverse ordering, and 'updated' for normal ordering
        ordering = ['-updated', '-created']

    def __str__(self):
        """
        Returns a string representation of the Room object.
        """
        host_str = self.host.username if self.host else "No Host"
        program_str = self.program.title if self.program else "No Program"
        return f"Room: {self.name} (Host: {host_str}, Program: {program_str})"


class Message(models.Model):  # One message can have only one room and user
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # CASCADE deletes all messages if the room is deleted
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    body = models.TextField()
    # It refreshes with the system time
    updated = models.DateTimeField(auto_now=True)
    # It refreshes the time only when its created
    created = models.DateTimeField(auto_now_add=True)

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
        # Include room name if available
        room_name = self.room.name if self.room else "Unknown Room"
        return f"Message by {user_str} in '{room_name}': \"{body_snippet}\""
