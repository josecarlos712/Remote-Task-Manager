import os
from django.conf import settings
from enum import Enum

from . import init_config


# IMPROVEMENT: Added structured logging configuration
# Configure logging
class LogLevel(Enum):
    CRITICAL = 50
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10
    NOTSET = 0


configuration = init_config.Configuration()  # Init for Configuration

# Logging configuration
login_tokens = {}  # Store valid tokens

# Other
CONFIG_PATH = 'config/programs.json'
VALID_TOKENS = []
SERVER_INITIALIZATION = True  # This variable is used to check if the server is loading. There is a function it needs to run once the server is loaded, and it needs to be run only once.
