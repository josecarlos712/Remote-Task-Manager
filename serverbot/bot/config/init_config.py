import configparser
import logging
import os
import re
from logging.handlers import TimedRotatingFileHandler

from django.conf import settings

from ..utils.utils import check_None, get_absolute_path


class Configuration():
    def __init__(self, config_path='configuration.ini'):
        self._system_info = {}
        self.logging = None
        self.config_path = f"bot/config/{config_path}"
        self._settings = {}
        self.initialize_server()

    # This function is executed on the start of the server to check if everything is okay.
    def initialize_server(self):
        if not self.logging:
            self.logging_configuration()

        # Perform startup tasks in the correct order
        self.logging.info("Starting API Server...")
        self.load_config()
        self.load_specifications()

        #self.check_files()
        self.check_DB()

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
            self.logging.debug(f"System info gathered: {info}")
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

        # Now that the file is guaranteed to exist, open and parse it
        try:
            # Assuming you are using configparser as the parsing logic is similar to INI
            config = configparser.ConfigParser()
            config.read(self.config_path)

            # Load settings into self._settings from configparser
            for section in config.sections():
                self._settings[section.lower()] = {}
                for key, value in config.items(section):
                    self._settings[section.lower()][key.lower()] = self.parse_value(value)  # Keep keys lowercase

            if self.logging:
                self.logging.debug(f"Configuration loaded successfully on {self.config_path}")

        except configparser.Error as e:
            if self.logging:
                self.logging.error(f"Error parsing configuration file {self.config_path}: {e}")
            else:
                print(f"Error parsing configuration file {self.config_path}: {e}")  # Fallback
            # Handle parsing errors (e.g., log a warning, use default values)
        except IOError as e:
            if self.logging:
                self.logging.error(f"Error reading configuration file {self.config_path}: {e}")
            else:
                print(f"Error reading configuration file {self.config_path}: {e}")  # Fallback
            # Handle file reading errors
        print(f"Configuration loaded: {self._settings}")

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
            self.logging.debug(f"CheckFiles: There was a problem creating the downloads folder on '{downloads_folder}'.")
            return False, f"CheckFiles: There was a problem creating the downloads folder on '{downloads_folder}'."

        return True, "CheckFiles OK"

    def check_DB(self):
        """Check for basic entrances on the database."""
        from ..models import Activity, User

        # Check if User System exists
        try:
            user = User.objects.get(username="System")
            if user:
                self.logging.debug(f"CheckDB: User System ({user}) exists.")
        except User.DoesNotExist:
            # If it doesn't exist, create it
            user, created = User.objects.get_or_create(
                username="System",
                defaults={
                    "first_name": "System",
                    "last_name": "System",
                    "email": "system@localhost",
                    "is_superuser": True,
                    "is_staff": True,
                }
            )
            self.logging.debug(f"CheckDB: Created User System ({user}).")

        # Check if the Activity 0 exists
        try:
            activity = Activity.objects.get(id=0)
            if activity:
                self.logging.debug(f"CheckDB: Activity 0 ({activity}) exists.")
        except Activity.DoesNotExist:
            # If it doesn't exist, create it
            activity, created = Activity.objects.get_or_create(
                id=0,
                defaults={
                    "user": user,
                    "name": "Default Activity",
                    "description": "Default Activity",
                    "date": "2023-01-01",
                    "hour": "00:00",
                }
            )
            self.logging.debug(f"CheckDB: Created Default Activity ({activity}).")

    def __getitem__(self, key, default=None):
        """Retrieves a configuration value given the key."""
        if key in self._settings:
            return self._settings.get(key, default if default else None)
        elif key in self._system_info:
            return self._system_info.get(key, default if default else "Unknown")
        else:
            self.logging.log(logging.ERROR, f"{key} is not in suported dicts on Configuration.")
            return default if default else None
