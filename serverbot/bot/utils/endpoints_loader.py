import os
import importlib
from ..config.config import logging

api_folder = os.path.join(os.path.dirname(__file__), '..')


def register_endpoint(app, api_path: str) -> bool:
    """ Helper function to import and register an endpoint. """
    if not api_path:
        return False  # Invalid path

    module_path = api_path.replace('/', '.')
    endpoint_name = os.path.basename(api_path)

    # Check if the path is an endpoint or a folder (a .py file of a folder with 'endpoint.py')
    if os.path.isfile(os.path.join(api_folder, f"{api_path}.py")):
        module_path = f'{module_path}'  # Single-file endpoint
    elif os.path.isdir(os.path.join(api_folder, api_path)):
        module_path = f'{module_path}.endpoint'  # sub-level
    else:
        return False  # Invalid path

    # Try to import and register the module
    try:
        module = importlib.import_module(module_path)
        if hasattr(module, 'register'):  # Check if the module has a 'register()' function
            if module.register(app, api_path) == 0:
                logging.debug(f"Registered endpoint: {endpoint_name}")
                return True
            else:
                logging.warn(f"Registration failed for '{endpoint_name}'")
        else:
            logging.warn(f"No 'register()' function found in '{module_path}'")
    except Exception as e:
        logging.error(f"Error loading '{module_path}': {e}")
    return False


def load_endpoints(app, relative_path: str):
    """
    Recursively loads API endpoints from the 'api' folder.

    - Each Python file (`*.py`) inside `api/` is treated as an independent endpoint.
    - Each folder inside `api/` represents a sub-level and must contain an `endpoint.py` file.
    - The `register()` function inside each file is called with `app` as an argument.

    :param app: Flask application instance.
    """
    excluded = {'__init__.py', 'blueprint_endpoint.py', '__pycache__', 'disabled'}

    # Register all the endpoints inside the folder
    for item in os.listdir(api_folder + '/' + relative_path):
        full_path = os.path.join(api_folder, relative_path, item)

        if item in excluded:
            continue  # Skip excluded files and directories

        if os.path.isfile(full_path) and item.endswith('.py') and not item.endswith('endpoint.py'):
            # Register single-file API endpoints
            api_path = relative_path + '/' + item[:-3]  # Remove .py extension
            register_endpoint(app, api_path=api_path)

        elif os.path.isdir(full_path):
            # Register complex API endpoints (folders with `endpoint.py` inside)
            api_path = relative_path + '/' + item
            register_endpoint(app, api_path=api_path)
