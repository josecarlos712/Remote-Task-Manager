import configparser
import logging
import os
import re
from logging.handlers import TimedRotatingFileHandler

from django.conf import settings
from django.utils import timezone

from ..utils.utils import check_None, get_absolute_path


class ConfigManager:
    def __init__(self, config_path="bot/config/configuration.ini"):
        self.config_path = config_path
        self.config = configparser.ConfigParser()  # Primary object for INI file I/O
        self._settings = {}  # Dictionary for easy access (lowercase keys)

        self._load_config_from_file()  # Load and populate on initialization

    def _load_config_from_file(self):
        """Internal method to load config from file and populate self.config and self._settings."""
        try:
            self.config.read(self.config_path)
            self._sync_config_to_settings_dict()  # Sync to the dictionary view
            print(f"Configuration loaded from {self.config_path}")
        except FileNotFoundError:
            print(f"Config file not found at {self.config_path}. Creating with default settings.")
            self._set_default_config()  # Set defaults in self.config and sync to _settings
            self._write_config_to_file()  # Save defaults to disk
        except configparser.Error as e:
            print(f"Error reading config file: {e}. Falling back to defaults.")
            self._set_default_config()  # Fallback to defaults

    def _set_default_config(self):
        """Populates self.config with default values and synchronizes to self._settings."""
        default_sections = {
            "serversettings": {"HOST": "0.0.0.0", "PORT": "5000", "DEBUG": "True"},
            "authenticationsettings": {"TOKEN_EXPIRATION_MINUTES": "60"},
            "loggingsettings": {"LOG_FILE": "logs/system.log", "MAX_LOG_SIZE_MB": "5"},
            "processmanagement": {"ALLOW_PROCESS_KILL": "True"},
            "paths": {"PATH_PROGRAMS": "bot/config/programs.json", "PATH_DOWNLOADS": "bot/downloads"},
            "systemmonitoring": {"CPU_USAGE_INTERVAL": "1"},
            "serverstatistics": {"LAST_COMMANDS_UPDATED": "0", "LAST_PROGRAMS_UPDATED": "0"}
        }
        # Clear existing sections before adding defaults to avoid conflicts
        for section in self.config.sections():
            self.config.remove_section(section)

        for section, options in default_sections.items():
            self.config.add_section(section)
            for key, value in options.items():
                self.config.set(section, key, value)
        self._sync_config_to_settings_dict()  # Ensure _settings dict is updated with defaults

    def _sync_config_to_settings_dict(self):
        """Synchronizes self.config (configparser object) to self._settings (dict)."""
        self._settings.clear()
        for section in self.config.sections():
            # Both section and key names can be converted to lowercase for the dict view
            self._settings[section.lower()] = {key.lower(): value for key, value in self.config.items(section)}

    def _write_config_to_file(self):
        """Writes the current state of the configparser object back to the INI file."""
        try:
            with open(self.config_path, 'w') as configfile:
                # Use self.config to write the data
                self.config.write(configfile)
            print(f"Configuration successfully written to {self.config_path}")
        except IOError as e:
            print(f"Error writing config file: {e}")

    # --- Public methods for accessing and updating settings ---

    def get_setting(self, section, key):
        """Get a setting value using lowercase section and key."""
        return self._settings.get(section.lower(), {}).get(key.lower())

    def update_and_save_setting(self, section, key, value):
        """Updates a setting in memory and saves it immediately to the file."""
        # 1. Update self.config (the object that writes to the file)
        # Use the lowercase section name for access, but configparser will write it back
        # with the casing it was initialized with or added (which is now lowercase for sections)
        if not self.config.has_section(section.lower()):  # Check existence using lowercase
            self.config.add_section(section.lower())  # Add using lowercase
        self.config.set(section.lower(), key, str(value))  # Convert value to string for INI file

        # 2. Update self._settings dictionary to keep it in sync
        # Ensure section exists in the dict, then update the key (lowercase)
        if section.lower() not in self._settings:
            self._settings[section.lower()] = {}
        self._settings[section.lower()][key.lower()] = str(value)

        # 3. Save the changes to the file
        self._write_config_to_file()
        print(f"Setting '{section}.{key}' updated to '{value}' and saved.")


class Configuration():
    def __init__(self, config_path='configuration.ini'):
        self._system_info = {}
        self.logging = None
        self.config_path = f"bot/config/{config_path}"
        self._settings: ConfigManager = None  # Use the ConfigManager class for INI file handling
        self.initialize_server()

    # This function is executed on the start of the server to check if everything is okay.
    def initialize_server(self):
        if not self.logging:
            self.logging_configuration()

        # Perform startup tasks in the correct order
        self.logging.info("Starting API Server...")
        self.load_config()
        self.load_specifications()

        # self.check_files()
        self.check_DB()  # Comment when doing 'magemigrations'

        self.logging.log(logging.INFO, "API Server started successfully.")

        return True, "Server initialized successfully."

    def logging_configuration(self) -> logging.Logger:  # Changed return type hint to logging.Logger
        log_file = get_absolute_path("logs/serverbot.log")  # Use the absolute path for the log file
        log_dir = os.path.dirname(log_file)  # Get the directory path

        # Create the log directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir,
                        exist_ok=True)  # Create the directory, exist_ok=True prevents error if it already exists

        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                # Creates a new log file every day and keeps 7 days
                TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=7, encoding="utf-8")
            ]
        )
        self.logging: logging.Logger = logging.getLogger(__name__)  # Use self.logger consistently

        # Log a message to confirm logging is configured
        self.logging.info("Logging configured.")

        return self.logging

    def load_specifications(self):
        import os
        import socket
        import json
        import platform
        import uuid
        import psutil
        import requests
        import subprocess

        system_info_path = get_absolute_path("logs/system_info.json")
        self._system_info = {}

        # In the specifications file there is a list of static values of the client (name, local ip, etc)
        def get_system_info() -> dict:
            """Gather all the info from the guest computer and store it on system_info.json"""
            try:
                # Basic System Info
                system_info = {
                    "computer_name": socket.gethostname(),
                    "local_ip": socket.gethostbyname(socket.gethostname()),
                    "mac_address": ':'.join(f"{(uuid.getnode() >> i) & 0xff:02x}" for i in range(0, 48, 8)),
                    "os": platform.system(),
                    "os_version": platform.version(),
                    "os_release": platform.release(),
                    "os_architecture": platform.architecture()[0],
                    "user_name": os.getlogin(),
                    "domain_name": os.getenv("USERDOMAIN", "Unknown")
                }

                # Hardware Info
                output = subprocess.check_output(
                    "wmic cpu get name", shell=True
                ).decode().strip().split("\n")[1:]  # Ignore the header row
                cpu_name = output[0].strip() if output else "Unknown"

                system_info.update({
                    "cpu": cpu_name,
                    "cpu_cores": os.cpu_count(),
                    "ram_size_mb": psutil.virtual_memory().total // (1024 ** 2),
                    "disk_size_gb": psutil.disk_usage('/').total // (1024 ** 3)
                })

                # GPU Info (Windows)
                if platform.system() == "Windows":
                    try:
                        output = subprocess.check_output(
                            "wmic path win32_videocontroller get caption", shell=True
                        ).decode().strip().split("\n")[1:]  # Ignore the header row

                        # Clean up output and filter empty/virtual entries
                        gpus = [gpu.strip() for gpu in output if gpu.strip() and "virtual" not in gpu.lower()]

                        system_info["gpu"] = gpus[0] if gpus else "Unknown"  # Return the first valid GPU found
                    except Exception:
                        system_info["gpu"] = "Unknown"

                # Public IP
                try:
                    system_info["public_ip"] = requests.get("https://api64.ipify.org", timeout=3).text
                except requests.RequestException:
                    system_info["public_ip"] = "Unknown"

                # Network Info (Windows)
                if platform.system() == "Windows":
                    try:
                        net_info = subprocess.check_output("ipconfig /all", shell=True).decode()
                        dns_servers = [line.split(":")[-1].strip() for line in net_info.split("\n") if
                                       "DNS Servers" in line]
                        system_info["dns_servers"] = dns_servers
                    except Exception:
                        system_info["dns_servers"] = []

                # BIOS & Motherboard Info (Windows)
                if platform.system() == "Windows":
                    try:
                        bios_version = \
                            subprocess.check_output("wmic bios get smbiosbiosversion",
                                                    shell=True).decode().strip().split(
                                "\n")[1].strip()
                        system_info["bios_version"] = bios_version
                    except Exception:
                        system_info["bios_version"] = "Unknown"

                    try:
                        motherboard = subprocess.check_output("wmic baseboard get product,manufacturer",
                                                              shell=True).decode().strip().split("\n")[1].strip()
                        system_info["motherboard"] = motherboard
                    except Exception:
                        system_info["motherboard"] = "Unknown"

                return system_info
            except Exception as e:
                return {"error": f"Failed to gather system info: {str(e)}"}

        def save_system_info(filename=system_info_path) -> dict:
            info = get_system_info()
            with open(filename, "w", encoding="utf-8") as file:
                json.dump(info, file, indent=4)
                file.close()
            #self.logging.debug(f"System info gathered: {info}")
            return info

        # Run the function to save the info
        if not os.path.exists(system_info_path):
            self.logging.log(logging.DEBUG, f"No system_info.json file. Creating one.")

        self._system_info = save_system_info()
        return self._system_info

    def load_config(self):
        """
        Loads the configuration file and parses key-value pairs.
        Creates the file with default content if it doesn't exist.
        """
        self.logging.debug(f"Loading configuration and specifications...\n{self._settings}")
        # Get the directory path of the config file
        config_dir = get_absolute_path(self.config_path)

        # Create the config directory if it doesn't exist (similar to logging)
        if config_dir and not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
                self.logging.debug(f"Created configuration directory: {config_dir}")
            except OSError as e:
                self.logging.error(f"Error creating configuration directory {config_dir}: {e}")
                # Depending on severity, you might want to raise the exception or exit

        # Check if the config file exists
        if not os.path.exists(self.config_path):
            self.logging.info(f"Configuration file not found: {self.config_path}. Creating with default content.")

            # Create the file with some default content (INI format example)
            default_content = """
                [API]
                api_key = YOUR_API_KEY_HERE
                # Add other default settings
            
                [System]
                log_level = INFO
                # Add other system settings
                """
            try:
                with open(self.config_path, 'w') as f:
                    f.write(default_content.strip())  # Write default content and remove leading/trailing whitespace
                    f.close()
                if self.logging:
                    self.logging.debug(f"Default configuration file created at: {self.config_path}")
                else:
                    print(f"Default configuration file created at: {self.config_path}")  # Fallback

            except IOError as e:
                if self.logging:
                    self.logging.error(f"Error creating default configuration file {self.config_path}: {e}")
                else:
                    print(f"Error creating default configuration file {self.config_path}: {e}")  # Fallback
                # If the file cannot be created, you might need to handle this error (e.g., exit the program)
                return  # Exit the function if file creation failed

        # Load the configuration file
        self._settings = ConfigManager(self.config_path)  # Use the ConfigManager class for INI file handling

        current_timestamp_str = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")

        self._settings.update_and_save_setting(
            'serverstatistics',  # Section name (lowercase as per your INI file)
            'last_commands_updated',  # Key name (matches your INI file, usually uppercase for constants)
            current_timestamp_str  # The new value (as a string)
        )
        self._settings.update_and_save_setting(
            'serverstatistics',  # Section name (lowercase as per your INI file)
            'last_programs_updated',  # Key name (matches your INI file, usually uppercase for constants)
            current_timestamp_str  # The new value (as a string)
        )
        # print(f"Configuration loaded: {self._settings}")

    def _write_config_to_file(self):
        """Writes the current state of the configparser object back to the INI file."""
        try:
            with open(self.config_path, 'w') as configfile:
                config = configparser.ConfigParser()
                # TODO Remove this when the configuration is finished
                # SystemStatistics->last_command_update stored in datetime format
                configfile['serverstatistics']['last_command_update'] = timezone.now()
                config.write(configfile)
            print(f"Configuration successfully written to {self.config_path}")
        except IOError as e:
            print(f"Error writing config file: {e}")

    def parse_value(self, value):
        """Converts string values to appropriate data types."""
        if value.lower() in ['true', 'false']:  # Boolean conversion
            return value.lower() == 'true'
        elif value.isdigit():  # Integer conversion
            return int(value)
        elif value.replace('.', '', 1).isdigit():  # Float conversion
            return float(value)
        return value  # Default to string

    def get_specification_info(self, key_path):
        """This is a get function for the computer speficications.

        This get function uses a nested key path with the format 'key.subkey.subsubkey'"""
        keys = key_path.split(".")  # Support dot notation for nested keys
        value = self._system_info

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]  # Go deeper into the dictionary
            else:
                return None  # Key not found

        return value

    def check_files(self):
        """Check for important directories and files inside the proyect."""
        self.logging.debug(f"Checking files...")
        # Checking downloads
        check_None(self._settings.get('paths'), "check_files() - paths is None")
        downloads_folder = get_absolute_path(self._settings.get('paths').get('path_downloads"'))
        is_absolute_path = bool(re.match(r"^[A-Za-z]:[\\/]", downloads_folder))

        if not os.path.isdir(downloads_folder) and is_absolute_path:
            # If the download folder doesn't exist, create it
            try:
                os.makedirs(downloads_folder, exist_ok=True)
                self.logging.debug(f"CheckFiles: Created downloads folder at {downloads_folder}")
            except Exception as e:
                self.logging.log(logging.ERROR, f"CheckFiles ERROR: Exception on os.makedirs - {e}")
                return False, f"CheckFiles ERROR: Exception on os.makedirs - {e}"
            self.logging.log(logging.DEBUG, "CheckFiles OK")
        elif not os.path.isdir(downloads_folder):
            self.logging.debug(
                f"CheckFiles: There was a problem creating the downloads folder on '{downloads_folder}'.")
            return False, f"CheckFiles: There was a problem creating the downloads folder on '{downloads_folder}'."

        return True, "CheckFiles OK"

    def check_DB(self):
        """Check for basic entrances on the database."""
        from ..models import Activity, User

        try:
            # --- Check/Create System User using get_or_create ---
            # get_or_create returns a tuple: (object, created_boolean)
            # defaults dictionary provides values for the object if it needs to be created
            user, created = User.objects.get_or_create(
                username="System",
                defaults={
                    'first_name': "System",
                    'last_name': "System",
                    'email': "system@localhost",
                    'is_superuser': True,
                    'is_staff': True,
                    'is_active': True,
                    'password': "josecarlos",  # Set a default password
                    # Add other default fields as necessary
                }
            )
            if created:
                self.logging.info(f"CheckDB: Created User System ({user}).")
            else:
                pass
                # self.logging.debug(f"CheckDB: User System already exists.")

        except Exception as e:
            self.logging.error(f"CheckDB ERROR: Exception on getting or creating User System - {e}", exc_info=True)
            return False, f"CheckDB ERROR: Exception on getting or creating User System - {e}"

            # --- Check/Create Activity 0 using get_or_create ---
            # Ensure the user object was successfully retrieved or created before proceeding
        if user is None:
            self.logging.error("CheckDB ERROR: System user is None after get_or_create.")
            return False, "CheckDB ERROR: System user is None after get_or_create."
        else:
            try:
                # Use pk=0 to specifically target the Activity with primary key 0
                activity, created = Activity.objects.get_or_create(
                    pk=0,  # Target the primary key with value 0
                    defaults={
                        'user': user,  # Link to the System user
                        'title': "System Activity",
                        'name': "System_Activity",
                        'description': "System activity",
                        # datetime field will use its default=timezone.now on creation
                    }
                )
                if created:
                    self.logging.info(f"CheckDB: Created Activity 0 ({activity}).")
                else:
                    pass
                    # self.logging.debug(f"CheckDB: Activity 0 already exists.")

                # If both checks/creations were successful, return True
                return True, "CheckDB OK"

            except Exception as e:
                self.logging.error(f"CheckDB ERROR: Exception on getting or creating Activity 0 - {e}", exc_info=True)
                return False, f"CheckDB ERROR: Exception on getting or creating Activity 0 - {e}"

    def __getitem__(self, section, key, default=None):
        """Retrieves a configuration value given the key."""
        # Get setting from the ConfigManager
        value = self._settings.get_setting(section, key)
        if value is None:
            # If the value is not found, return the default value
            return default
        # Convert the value to its appropriate type
        return self.parse_value(value)
