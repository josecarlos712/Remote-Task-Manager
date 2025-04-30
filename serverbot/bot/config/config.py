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
logging = configuration.logging  # Make the logger global by creating a static variable

# Logging configuration
login_tokens = {}  # Store valid tokens

# Other
CONFIG_PATH = 'config/programs.json'
VALID_TOKENS = []
