import json

import requests
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.urls import get_resolver
from rest_framework.authtoken.models import Token

from . import urls
import logging

from .utils import APIResponse
from .utils.commands_utils import *
from .utils.programs_utils import *
from .utils.activity_utils import *
from .utils.messages_utils import *
from .utils.clients_utils import *
from .utils.user_utils import *
from .utils.APIResponse import (
    SuccessResponse,
    BadMethodErrorResponse,
    InternalErrorResponse,
    NotFoundResponse,
    ErrorResponse,
    ForbiddenErrorResponse, ValidationErrorResponse, UnauthorizedResponse, check_None_API, BadRequestResponse,
)
from .models import Command, Client, UserSettings, user_to_dict

from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect, csrf_exempt

from .utils.utils import check_None
from .utils.clients_utils import send_client_get_request, send_client_post_request

# Dict to store avalilable and loaded commands to avoid DB queries.
logger = logging.getLogger(__name__)


# ---- Command API ----
@login_required
@csrf_protect
@require_POST  # Only allows POST requests
def api_update_commands_list(request):
    """
    API URL: api/command/list
    API endpoint to check if the currently logged-in user is allowed
    to access a specific client based on its ID.

    Requires authentication, CSRF token, and is a POST request.
    Expects JSON body with 'client_id'.
    """
    try:
        # Attempt to parse the JSON data from the request body
        data = json.loads(request.body)
        logger.debug(f"api_update_commands_list() - Received data: {data}")

    except json.JSONDecodeError:
        logger.error("api_update_commands_list() - Invalid JSON format received.")
        return ErrorResponse("Invalid JSON format.", 400).to_response()

    # Get the client_id from the request data
    client_id = data.get('client_id')

    # Validate the presence of client_id
    response, code = check_None_API(client_id, "api_update_commands_list() - Missing 'client_id' in request data.")
    if code != 200:
        return response

    # Retrieve the Client object
    logger.debug(f"api_update_commands_list() - Attempting to retrieve client with ID: {client_id}")
    try:
        client_obj = Client.objects.get(pk=client_id)
        logger.debug(f"api_update_commands_list() - Successfully retrieved client: {client_obj}")

    except ObjectDoesNotExist:
        logger.warning(f"api_update_commands_list() - Client with ID '{client_id}' not found.")
        return NotFoundResponse("client_id").to_response()

    except MultipleObjectsReturned:
        # Should not happen for primary key lookup, but included for robustness
        logger.error(f"api_update_commands_list() - Multiple clients found for ID '{client_id}'. Database error?")
        return InternalErrorResponse("Multiple clients found for this ID.").to_response()

    except Exception as e:
        # Catch any other potential database errors during retrieval
        logger.error(f"api_update_commands_list() - Error retrieving client '{client_id}': {e}", exc_info=True)
        return InternalErrorResponse("A unexpected exception occurred while retrieving the client.").to_response()

    # --- Check User Allowance for the Client ---
    user = request.user  # Get the currently authenticated user
    if not user:
        logger.debug("api_update_commands_list() - User is not authenticated.")
        return UnauthorizedResponse("User is not authenticated.").to_response()

    # Use the is_user_allowed method of the Client model
    if not client_obj.is_user_allowed(user):
        logger.debug(
            f"api_update_commands_list() - User '{user.username}' is not allowed to access client {client_obj}.")
        # If the user is allowed, return a success response
        return UnauthorizedResponse(f"{user} is not allowed to access {client_obj}.").to_response()  # 200 OK

    # --- Update the commands list for the client ---
    # Send the GET request to the client application on the endpoint 'api/command/list'
    commands_api_endpoint = "api/command/list"  # Endpoint to fetch the command list
    command_list, status_code = send_client_get_request(client_obj, commands_api_endpoint)

    # Check if the command list was successfully retrieved
    if status_code != 200:
        logger.error(f"api_update_commands_list() - Failed to retrieve command list from client {client_obj}.")
        return InternalErrorResponse("Failed to retrieve command list from the client.").to_response()

    logger.debug(f"api_update_commands_list() - Command list for client {client_obj}: {command_list}")

    # Update the Command DB with the new command list
    sync_status = update_commands_list(client_obj, command_list)

    if sync_status:
        logger.info(f"api_update_commands_list() - Command list synchronized successfully for client {client_obj}.")
        return SuccessResponse("Command list synchronized successfully.").to_response()
    else:
        logger.error(f"api_update_commands_list() - Failed to synchronize command list for client {client_obj}.")
        return InternalErrorResponse("Failed to synchronize command list.").to_response()


@login_required
@csrf_protect
@require_POST
def api_execute_command(request):
    """
        API URL: api/command/execute
        Handles command execution requests via API.
        Requires authentication.
        Receives JSON data with 'client_id', 'command_id', and optional 'args'/'kwargs'.
        Verifies if the requesting user is allowed to access the specified client.
        Forwards the command execution request to the client application's API.
        """
    _method = 'POST'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method
    command_endpoint = "api/command/execute/"  # Endpoint to forward the command to the client application

    try:
        data = json.loads(request.body)
        logger.debug(f"api_command() - Received data: {data}")

    except json.JSONDecodeError:
        logger.error("api_command() - Invalid JSON format received.")
        api_response = ErrorResponse(message="Datos JSON inválidos.")
        return JsonResponse(api_response.to_dict(), status=400)

    # Get required data from the request
    client_id = data.get('client_id')
    command_id = data.get('command_id')
    args = data.get('args', [])  # Default to empty list
    kwargs = data.get('kwargs', {})  # Default to empty dict

    # Validate required fields in the incoming request
    expected_fields = ['client_id', 'command_id']
    for field in expected_fields:
        if field not in data:
            logger.warning(f"api_command() - Missing '{field}' in request data.")
            api_response = BadRequestResponse(message=f"api_command() - Missing '{field}' in request data.")
            return JsonResponse(api_response.to_dict(), status=400)

    # Basic type checks for args and kwargs
    if not isinstance(args, list):
        logger.warning(f"api_command() - 'args' field is not a list: {args}")
        api_response = BadRequestResponse(message="'args' debe ser una lista.")
        return JsonResponse(api_response.to_dict(), status=400)

    if not isinstance(kwargs, dict):
        logger.warning(f"api_command() - 'kwargs' field is not a dictionary: {kwargs}")
        api_response = BadRequestResponse(message="'kwargs' debe ser un diccionario.")
        return JsonResponse(api_response.to_dict(), status=400)

    # Retrieve the Client object
    logger.debug(f"api_command() - Attempting to retrieve client with ID: {client_id}")
    try:
        client_obj = Client.objects.get(pk=client_id)
        logger.debug(f"api_command() - Successfully retrieved client: {client_obj}")

    except ObjectDoesNotExist:
        logger.warning(f"api_command() - Client with ID '{client_id}' not found.")
        api_response = NotFoundResponse(f"Cliente con ID '{client_id}' no encontrado.")
        return JsonResponse(api_response.to_dict(), status=404)

    except MultipleObjectsReturned:
        # Should not happen for primary key lookup, but included for robustness
        logger.error(f"api_command() - Multiple clients found for ID '{client_id}'. Database error?")
        api_response = InternalErrorResponse("Error interno: Múltiples clientes encontrados.")
        return JsonResponse(api_response.to_dict(), status=500)

    except Exception as e:
        logger.error(f"api_command() - Error retrieving client '{client_id}': {e}", exc_info=True)
        api_response = InternalErrorResponse("Ocurrió un error al obtener el cliente.")
        return JsonResponse(api_response.to_dict(), status=500)

    # --- Check User Allowance for the Client ---
    user = request.user  # Get the currently authenticated user

    # Use the is_user_allowed method of the Client model
    if not client_obj.is_user_allowed(user):
        logger.warning(
            f"api_command() - User '{user.username}' is not on the allowance list {client_obj.allowed_users}, so is not allowed to access client {client_obj}.")
        api_response = ForbiddenErrorResponse(message="No tienes permiso para acceder a este cliente.")
        return JsonResponse(api_response.to_dict(), status=403)

    # Get user api key stored in the user
    # TODO: Get client api key from UserSettings
    # Get the UserSettings from the user
    user_settings = user.usersettings_set.first()
    if user_settings:
        # Get the client API keys dict from the UserSettings
        client_api_key_dict = user_settings.client_api_keys
        # Look for the client API key in the dict using the name of the client
        client_api_key = client_api_key_dict.get(client_obj.name)
        if not client_api_key:
            logger.error(
                f"api_command() - Client API key not found for client {client_obj.name} in user's ({user}) settings: {client_api_key_dict}.")
            return UnauthorizedResponse("Client API key not found.").to_response()
    # client_api_key = getattr(settings, 'CLIENT_API_SECRET_KEY', None)

    # --- Forward the command execution request to the Client Application ---
    # TODO Replace with the send API request function
    client_api_url = f"http://{client_obj.local_ip}:{client_obj.port}/{command_endpoint}"

    # Prepare the payload to send to the client application
    client_payload = {
        'command_id': command_id,
        'args': args,
        'kwargs': kwargs,
    }

    # Prepare the headers, including the custom API key header
    # Use a custom header name like 'X-Client-API-Key'
    headers = {
        'Content-Type': 'application/json',
        'X-Client-API-Key': client_api_key  # Add your secret key here
    }

    logger.debug(
        f"api_command() - Forwarding command '{command_id}' to client {client_obj} at {client_api_url} with payload: {client_payload}")

    try:
        # Make the POST request to the client application's API
        # Pass the headers dictionary to the requests.post call
        client_response = requests.post(client_api_url, json=client_payload, headers=headers,
                                        timeout=10)  # Added headers

        # Check the HTTP status code of the response from the client
        client_response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        # Attempt to parse the JSON response from the client application
        # Assuming the client application's API returns JSON
        client_result = client_response.json()
        logger.info(f"api_command() - Received response from client {client_obj}: {client_result}")

        # Forward the client's response back to the original web client
        # TODO: Review the structure of client_result and potentially wrap it
        # in a standard APIResponse format if the client's response format is inconsistent.
        # For now, we'll return the client's JSON response directly.
        return JsonResponse(client_result, status=client_response.status_code)  # Use the client's status code

    except requests.exceptions.Timeout:
        logger.error(f"api_command() - Request to client {client_obj} at {client_api_url} timed out.")
        api_response = InternalErrorResponse(f"La solicitud al cliente {client_obj} excedió el tiempo de espera.")
        return JsonResponse(api_response.to_dict(), status=504)  # 504 Gateway Timeout

    except requests.exceptions.ConnectionError:
        logger.error(f"api_command() - Could not connect to client {client_obj} at {client_api_url}.")
        api_response = InternalErrorResponse(f"No se pudo conectar con el cliente {client_obj}.")
        return JsonResponse(api_response.to_dict(), status=503)  # 503 Service Unavailable

    except requests.exceptions.RequestException as e:
        # Catch any other requests-related errors (e.g., HTTPError from raise_for_status)
        logger.error(f"api_command() - Error forwarding request to client {client_obj} at {client_api_url}: {e}",
                     exc_info=True)
        try:
            # Attempt to get error details from the client response body if available
            error_details = client_response.json()
        except json.JSONDecodeError:
            error_details = client_response.text  # Fallback to text if not JSON

        api_response = InternalErrorResponse(
            f"Error al comunicar con el cliente {client_obj}. Client responded with status {client_response.status_code}: {error_details}")
        return JsonResponse(api_response.to_dict(),
                            status=client_response.status_code if client_response.status_code >= 400 else 500)  # Use client's error status or 500

    except Exception as e:
        # Catch any other unexpected errors during the forwarding process
        logger.error(
            f"api_command() - An unexpected error occurred during client communication for command '{command_id}' on client {client_obj}: {e}",
            exc_info=True)
        api_response = InternalErrorResponse(
            f"Ocurrió un error inesperado al procesar el comando '{command_id}'.", error=str(e))
        return JsonResponse(api_response.to_dict(), status=500)


# Get all commands from the database for the request.user
@login_required
@csrf_protect
@require_GET
def api_get_command_list(request):
    """
    API URL: api/command/list
    API endpoint to get the list of commands for a specific client.
    Requires authentication and CSRF token.
    Expects JSON body with 'client_id'.
    """
    # This view only supports GET requests
    _method = 'GET'
    if not request:
        return _method

    # Get the client_id from the request data
    client_id = request.user.id

    # Get commands from user
    commands, code = get_command_list_by_user(client_id)
    if code != 200:
        logger.error(f"api_get_command_list() - Failed to retrieve command list for user {client_id}.")
        return NotFoundResponse(commands).to_response()
    logger.debug(f"api_get_command_list() - Successfully retrieved command list for user {client_id}.")
    # Convert the command list to a list of dictionaries
    command_list = [command.to_dict() for command in commands]
    # Return the command list as a JSON response
    return SuccessResponse("Successfully retrieved command list for user {client_id}.", command_list)  # 200 OK


# ---- Program API ----
@login_required
@csrf_protect
@require_POST
def api_update_program_list(request):
    """
    API URL: api/program/list
    API endpoint to update the program list for a specific client.
    Requires authentication and CSRF token.
    Expects JSON body with 'client_id'.
    """
    _method = 'POST'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    update_programs_list_endpoint = "api/program/list"  # Endpoint to forward the command to the client application

    try:
        data = json.loads(request.body)
        logger.debug(f"api_update_program_list() - Received data: {data}")

        # Get the client_id from the request data
        client_id = data.get('client_id')

        # Validate the presence of client_id
        client_id_response = check_None(client_id, "api_update_program_list() - Missing 'client_id' in request data.")
        if client_id_response:
            return client_id_response
    except json.JSONDecodeError:
        logger.error("api_update_program_list() - Invalid JSON format received.")
        return ErrorResponse(message="Invalid JSON format received.").to_response()

    # Send POST request to client.
    response, code = send_client_post_request(client_id, request.user, update_programs_list_endpoint, data)
    # Client response from 'api/program/list' shoul look like this:
    # {
    #     "program_1": {
    #         "name": "Program 1",
    #         "title": "Title of Program 1",
    #         "description": "Description of Program 1"
    #     }
    # }
    if code == 200:
        # If the request was successful, Update the program list in the database
        # Get p
        update_programs_list(client_id, response)

        logger.debug(f"api_update_program_list() - Successfully updated program list for client {client_id}.")
        return JsonResponse(response, status=200)


@login_required  # Requires the user to be logged in
@csrf_protect  # Requires a valid CSRF token for POST requests
@require_POST  # Only allows POST requests
def refresh_processes_status(request):
    """
    API URL: api/program/status/refresh (or similar, based on your urls.py)
    API endpoint to refresh the 'available' and running status of programs
    for a specific client by making a GET request to the client's
    '/api/program/status' endpoint.

    Requires authentication and CSRF token.
    Expects JSON body with 'client_id'.
    """
    # This view only supports POST requests
    _method = 'POST'

    try:
        data = json.loads(request.body)
        logger.debug(f"refresh_processes_status() - Received data: {data}")

    except json.JSONDecodeError:
        logger.error("refresh_processes_status() - Invalid JSON format received.")
        return ErrorResponse("Invalid JSON format received.").to_response()

    # Get required data from the request
    client_id = data.get('client_id')

    # Validate required fields in the incoming request
    if not client_id:
        logger.warning("refresh_processes_status() - Missing 'client_id' in request data.")
        return BadRequestResponse("Falta el ID del cliente.").to_response()

    #

    # --- Update Program status in the database based on client response ---
    # Client response from 'api/program/status' shoul look like this:
    # {
    #     "program_1": {
    #         "available": true
    #     }
    # }
    # Send the GET request to the client application on the endpoint 'api/program/status' to get the programs status
    programs_status, code = send_client_get_request(client_id, "api/program/status")
    if code != 200:
        logger.error(
            f"refresh_processes_status() - Failed to retrieve program status from client {client_id}. {programs_status}")
        return InternalErrorResponse(
            f"Failed to retrieve program status from the client. {programs_status}").to_response()

    # Update the program status in the database
    response, code = update_programs_list(client_id, programs_status)
    if code == 200:
        logger.debug(f"refresh_processes_status() - Successfully updated program status for client {client_id}.")
        return JsonResponse(response, status=200)
    else:
        logger.error(f"refresh_processes_status() - Failed to update program status for client {client_id}.")
        return InternalErrorResponse("Failed to update program status.").to_response()


# ---- User Registration and Authentication API ----
@csrf_protect
@require_POST
def api_register(request):
    """
        Handles user registration via API.
        Receives JSON data with 'username', 'email', 'password', and optional 'first_name' and 'last_name'.
        Validates it, creates a new user, and logs them in.
        """
    if request.method == "POST":
        try:
            # Attempt to parse the JSON data from the request body
            data = json.loads(request.body)

            # Extract data fields, providing default None if a key is missing
            username = data.get('username')  # This field is required
            email = data.get('email')  # This field is required
            password = data.get('password')  # This field is required
            confirm_password = data.get('confirm_password')  # This field is required
            first_name = data.get('first_name', 'Jhon')  # Default to empty string if not provided
            last_name = data.get('last_name', 'Doe')  # Default to empty string if not provided

            errors = {}  # Dictionary to collect validation errors

            # --- Server-Side Validation ---
            # Check if required fields are present and not empty
            if not username:
                errors['username'] = ['El nombre de usuario es obligatorio.']
            if not email:
                errors['email'] = ['El correo electrónico es obligatorio.']
            if not password:
                errors['password'] = ['La contraseña es obligatoria.']

            # Validate password length
            if password and len(password) < 8:
                # Add error only if password was provided but is too short
                errors['password'] = errors.get('password', []) + [
                    'La contraseña debe tener al menos 8 caracteres.']

            # Check if passwords match
            if password != confirm_password:
                errors['confirm_password'] = ['Las contraseñas no coinciden.']

            # Check if username already exists
            if username and User.objects.filter(username__iexact=username).exists():
                # Use iexact for case-insensitive check
                errors['username'] = errors.get('username', []) + ['El nombre de usuario ya está en uso.']

            # Check if email already exists
            if email and User.objects.filter(email__iexact=email).exists():
                # Use iexact for case-insensitive check
                errors['email'] = errors.get('email', []) + ['El correo electrónico ya está registrado.']

            # If there are any validation errors, return a JSON response with errors
            if errors:
                logging.warning(f"register_view() - Registration validation failed: {errors}")
                error_keys = ','.join(f"{k}" for k in errors.keys())
                api_response = APIResponse.ValidationErrorResponse(f"{error_keys}")
                return JsonResponse(api_response.to_dict(), status=400)  # 400 Bad Request

            # Use create_user which handles password hashing securely
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                # When creating a usser, a UserSettings is created automatically

            except Exception as e:
                # Catch potential errors during user creation (e.g., database issues)
                errors['non_field_errors'] = ['Ocurrió un error al crear el usuario.']
                api_response = APIResponse.InternalErrorResponse(
                    error=f"register_view() - Ocurrió un error al crear el usuario. {e}")
                return JsonResponse(api_response.to_dict(), status=500)  # 500 Internal Server Error

            # Authenticate the newly created user
            authenticated_user = authenticate(request, username=username, password=password)

            if authenticated_user is not None:
                login(request, authenticated_user)  # Log the user in
                api_response = APIResponse.SuccessResponse(message="register_view() - Registro exitoso.")
                return JsonResponse(api_response.to_dict(),
                                    status=201)  # 201 Created - Indicates successful creation
            else:
                # This case should ideally not happen after successful create_user and authenticate,
                # but it's a fallback for unexpected authentication issues.
                errors['non_field_errors'] = ['Error de autenticación después del registro.']
                api_response = APIResponse.InternalErrorResponse(
                    error="register_view() - Error de autenticación después del registro.")
                return JsonResponse(api_response.to_dict(), status=500)

        except json.JSONDecodeError:
            # Handle invalid JSON in the request body
            api_response = APIResponse.ErrorResponse(message="register_view() - Datos JSON inválidos.")
            return JsonResponse(api_response.to_dict(), status=400)  # 400 Bad Request

        except Exception as e:
            # Catch any other unexpected errors
            api_response = APIResponse.InternalErrorResponse(
                error=f"register_view() - Ocurrió un error inesperado durante el registro. - {e}")
            return JsonResponse(api_response.to_dict(), status=500)  # 500 Internal Server Error

    else:
        # Handle requests that are not POST
        api_response = APIResponse.BadMethodErrorResponse(method=request.method, expected_method="POST")
        return JsonResponse(api_response.to_dict(), status=405)  # 405 Method Not Allowed


@csrf_protect
@require_POST
def api_logout(request):
    """
    Handles user logout via API and returns a JSON response.
    If the user is logged in, it logs them out and returns a success message.
    """
    if request.user.is_authenticated:
        logout(request)
        return JsonResponse({'success': True, 'message': 'Logged out successfully.'}, status=200)
    else:
        # User was not logged in
        return JsonResponse({'success': False, 'message': 'No user was logged in.'}, status=400)


@csrf_protect
@require_POST
def api_login(request):
    """
    Handles user login via API.
    Receives JSON data with 'username' and 'password'.
    Validates the credentials, logs in the user and returns a JSON response.
    """
    _method = 'POST'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')

            if not username or not password:
                return JsonResponse({'success': False, 'error': 'Username and password are required.'}, status=400)

            # Check the credentials on the users database
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                # If you were planning to use tokens, you can generate and include them here
                # Example (if you have a Token model):
                from rest_framework.authtoken.models import Token
                token, _ = Token.objects.get_or_create(user=user)
                return JsonResponse({'success': True, 'token': token.key}, status=200)  # Include token in response
                # return JsonResponse({'success': True}, status=200)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid username or password.'},
                                    status=401)  # 401 Unauthorized
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            print("Error during login:", e)  # Log the error for debugging
            return JsonResponse({'success': False, 'error': 'An error occurred during login.'}, status=500)
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method.'},
                            status=405)  # 405 Method Not Allowed


# ---- Activity API ----
# Endpoint to get a list of every activity
@require_GET
@csrf_exempt
def api_get_activity_list(request):
    """
    API URL: api/activities/list
    API endpoint to get the list of activities.
    Does not require authentication or CSRF token.
    """
    # This view only supports GET requests
    _method = 'GET'
    if not request:
        return _method

    if request.method == 'GET':
        # Get the list of activities from the database
        # Get the list of activities from the database
        activities, code = get_activities()
        if code != 200:
            logger.error(f"get_activity_list() - Failed to retrieve activity list.")
            return InternalErrorResponse("Failed to retrieve activity list.").to_response()

        # Convert the QuerySet of Activity objects into a list of dictionaries using to_dict()
        activity_list_data = [activity.to_dict() for activity in activities]

        # If the request was successful, return the list of activities
        logger.debug(f"get_activity_list() - Successfully retrieved activity list: {activity_list_data}")
        return SuccessResponse("Successfully retrieved activity list.", activity_list_data).to_response()  # 200 OK
    else:
        return BadMethodErrorResponse(method=request.method,
                                      expected_method=_method).to_response()  # 405 Method Not Allowed


# Endpoint to get an activity by its ID
@require_POST
@csrf_exempt
def api_get_activity_by_id(request):
    """
    API URL: api/activities/
    API endpoint to get a message by its ID.
    Receives JSON data with 'activity_id'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the activity_id from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"get_activity_by_id() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("get_activity_by_id() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the activity_id from the JSON body
        activity_id = data.get('activity_id')

        # Validate the presence of activity_id
        response, code = check_None_API(activity_id,
                                        "get_activity_by_id() - Missing 'activity' in request data.")
        if code != 200:
            return response

        # Get the activity from the database
        activity, code = get_activity_by_id(activity_id)
        if code != 200:
            logger.error(f"get_activity_by_id() - Failed to retrieve activity with ID {activity_id}.")
            return InternalErrorResponse(activity).to_response()
        # Convert the Activity object into a dictionary using to_dict()
        activity_data = activity.to_dict()
        # If the request was successful, return the activity data
        logger.debug(f"get_activity_by_id() - Successfully retrieved activity data: {activity_data}")
        return SuccessResponse("Successfully retrieved activity data.", activity_data).to_response()


# Endpoint to get a list of activities from a user
@require_POST
@csrf_exempt
def api_get_activity_list_from_user(request):
    """
    API URL: api/activities/list/user
    API endpoint to get the list of activities.
    Requires authentication and CSRF token.
    Expects JSON body with 'user_id'.
    """
    # This view only supports GET requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the user from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"get_activity_list_from_user() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("get_activity_list_from_user() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the user from the JSON body
        user_id = data.get('user_id')

        # Validate the presence of user
        response, code = check_None_API(user_id, "get_activity_list_from_user() - Missing 'user' in request data.")
        if code != 200:
            return response

        # Get the list of activities from the database
        activities, code = get_activities_by_user(user_id)
        if code != 200:
            logger.error(f"get_activity_list_from_user() - Failed to retrieve activities for user {user_id}.")
            return InternalErrorResponse(activities).to_response()
        # Convert the QuerySet of Activity objects into a list of dictionaries using to_dict()
        activity_list_data = [activity.to_dict() for activity in activities]
        # If the request was successful, return the list of activities
        logger.debug(f"get_activity_list() - Successfully retrieved activity list: {activity_list_data}")
        return SuccessResponse("Successfully retrieved activity list.", activity_list_data).to_response()  # 200 OK


# Endpoint to create an activity
@require_POST
@csrf_protect
@login_required
def api_create_activity(request):
    """
    API URL: api/activities/create
    API endpoint to create a new activity.
    Requires authentication and CSRF token.
    Expects JSON body with 'title' and 'description'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the activity data from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"create_activity() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("create_activity() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Verify the parameters
        expected_fields = ['activity_title', 'activity_description']
        for field in expected_fields:
            if field not in data:
                logger.warning(f"create_activity() - Missing '{field}' in request data.")
                return BadRequestResponse(f"create_activity() - Missing '{field}' in request data.").to_response()

        # Add to parameters variable the available fields in the request
        parameters = {}
        for key in data.keys():
            if key in expected_fields:
                parameters[key] = data[key]

        parameters['user_id'] = request.user.id
        # activity_name is the title in lowercase with spaces replaced by underscores
        parameters['name'] = parameters['title'].lower().replace(" ", "_")

        # Validate the presence of activity_title
        response, code = check_None_API(parameters['title'],
                                        "create_activity() - Missing 'activity_name' in request data.")
        if code != 200:
            return response

        response, code = check_None_API(parameters['description'],
                                        "create_activity() - Missing 'activity_description' in request data.")
        if code != 200:
            parameters['description'] = ""

        # Create the activity in the database
        activity, code = create_activity(parameters)
        # Check if the code starts with 2xx
        if code == 201:
            logger.info(f"create_activity() - Activity '{activity}' created successfully.")
            # Convert the Activity object into a dictionary using to_dict()
            activity_data = activity.to_dict()
            # If the request was successful, return the activity data
            logger.debug(f"create_activity() - Successfully created activity data: {activity_data}")
            return SuccessResponse("Successfully created activity data.", activity_data).to_response()
        if code != 200:
            logger.error(f"create_activity() - Failed to create activity with name {parameters['name']}.")
            return InternalErrorResponse(activity).to_response()


# Endpoint to update an activity given the id and the parameters
@require_POST
@csrf_protect
@login_required
def api_update_activity(request):
    """
    API URL: api/activities/update
    API endpoint to update an activity by its ID.
    Receives JSON data with 'activity_id', 'activity_title', and 'activity_description'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the activity data from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"update_activity_by_id() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("update_activity_by_id() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Check if the activity_id is present in the request
        activity_id = data.get('activity_id')
        response, code = check_None_API(activity_id,
                                        "update_activity_by_id() - Missing 'activity_id' in request data.")
        if code != 200:
            return response

        # Optional fields to be updated
        expected_fields = ['title', 'description']

        # Add to parameters variable the available fields in the request
        parameters = {}
        for key in data.keys():
            if key in expected_fields:
                parameters[key] = data[key]

        # Update the activity in the database
        activity, code = update_activity(activity_id, parameters)
        if code != 200:
            logger.error(f"update_activity_by_id() - Failed to update activity with ID {activity_id}.")
            return InternalErrorResponse(activity).to_response()
        # Convert the Activity object into a dictionary using to_dict()
        activity_data = activity.to_dict()
        # If the request was successful, return the activity data
        logger.debug(f"update_activity_by_id() - Successfully updated activity data: {activity_data}")
        return SuccessResponse("Successfully updated activity data.", activity_data).to_response()


# Endpoint to delete an activity given the id
@require_POST
@csrf_protect
@login_required
def api_delete_activity(request):
    """
    API URL: api/activities/delete
    API endpoint to delete an activity by its ID.
    Receives JSON data with 'activity_id'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the activity_id from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"delete_activity_by_id() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("delete_activity_by_id() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the activity_id from the JSON body
        activity_id = data.get('activity_id')

        # Validate the presence of activity_id
        response, code = check_None_API(activity_id,
                                        "delete_activity_by_id() - Missing 'activity_id' in request data.")
        if code != 200:
            return response

        # Delete the activity from the database
        activity, code = delete_activity(activity_id)
        if code != 200:
            logger.error(f"delete_activity_by_id() - Failed to delete activity with ID {activity_id}.")
            return InternalErrorResponse(activity).to_response()
        # If the request was successful, return the activity data
        logger.debug(f"delete_activity_by_id() - Successfully deleted activity with ID: {activity_id}")
        return SuccessResponse(f"Successfully deleted activity with ID: {activity_id}").to_response()


# ---- Message API ----
# Endpoint to get a message from its ID
@require_POST
@csrf_exempt
def api_get_message_by_id(request):
    """
    API URL: api/messages/
    API endpoint to get a message by its ID.
    Receives JSON data with 'message_id'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the message_id from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"get_message_by_id() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("get_message_by_id() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the message_id from the JSON body
        message_id = data.get('message_id')

        # Validate the presence of message_id
        response, code = check_None_API(message_id,
                                        "get_message_by_id() - Missing 'message' in request data.")
        if code != 200:
            return response

        # Get the message from the database
        message, code = get_message_by_id(message_id)
        if code != 200:
            logger.error(f"get_message_by_id() - Failed to retrieve message with ID {message_id}.")
            return InternalErrorResponse(message).to_response()
        # Convert the Message object into a dictionary using to_dict()
        message_data = message.to_dict()
        # If the request was successful, return the activity data
        logger.debug(f"get_message_by_id() - Successfully retrieved activity data: {message_data}")
        return SuccessResponse("Successfully retrieved activity data.", message_data).to_response()


# Endpoint to get all the messages from a user
@require_POST
@csrf_exempt
def api_get_message_list_from_user(request):
    """
    API URL: api/messages/list/user
    API endpoint to get the list of messages.
    Requires authentication and CSRF token.
    Expects JSON body with 'user_id'.
    """
    # This view only supports GET requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the user from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"get_message_list_from_user() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("get_message_list_from_user() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the user from the JSON body
        user_id = data.get('user_id')

        # Validate the presence of user
        response, code = check_None_API(user_id, "get_message_list_from_user() - Missing 'user' in request data.")
        if code != 200:
            return response

        # Get the list of messages from the database
        messages, code = get_messages_from_user(user_id)
        if code != 200:
            if code == 404:  # No messages found for the user (get_messages_from_user returns 404 if no messages)
                logger.info(
                    f"get_message_list_from_user() - No messages found for user {user_id}. Returning empty list.")
                # Return a SuccessResponse with an empty list in the 'data' field
                api_response_data = SuccessResponse(f"No messages found for user {user_id}.",
                                                    []).to_dict()
                return JsonResponse(api_response_data, status=200)  # Return 200 OK with empty data
            else:  # Other errors (e.g., database error from get_messages_from_user)
                logger.error(
                    f"get_message_list_from_user() - Failed to retrieve messages for user {user_id}.")
                api_response = InternalErrorResponse("Ocurrió un error interno al obtener los mensajes.")
                return JsonResponse(api_response.to_dict(), status=500)  # 500 Internal Server Error

        # Convert the QuerySet of Message objects into a list of dictionaries using to_dict()
        message_list_data = [message.to_dict() for message in messages]

        # If the request was successful, return the list of messages
        logger.debug(f"get_message_list() - Successfully retrieved message list: {message_list_data}")
        return SuccessResponse("Successfully retrieved message list.", message_list_data).to_response()  # 200 OK
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method.'},
                            status=405)  # 405 Method Not Allowed


# Endpoint to get all the messages from an activity
@require_POST
@csrf_exempt
def api_get_message_list_from_activity(request):
    """
    API URL: api/messages/list/activty
    API endpoint to get the list of messages.
    Requires authentication and CSRF token.
    Expects JSON body with 'activity_id'.
    """
    # This view only supports GET requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the activity from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"get_message_list_from_activity() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("get_message_list_from_activity() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the activity from the JSON body
        activity_id = data.get('activity_id')

        # Validate the presence of activity_id
        response, code = check_None_API(activity_id,
                                        "get_message_list_from_activity() - Missing 'activity' in request data.")
        if code != 200:
            return response

        # Get the list of messages from the database
        messages, code = get_messages_from_activity(activity_id)
        if code != 200:
            if code == 404:
                # No messages found for the activity (get_messages_from_activity returns 404 if no messages)
                logger.info(
                    f"get_message_list_from_activity() - No messages found for activity {activity_id}. Returning empty list.")
                # Return a SuccessResponse with an empty list in the 'data' field
                return SuccessResponse(messages, []).to_response()
            else:  # Other errors (e.g., database error from get_messages_from_activity)
                logger.error(
                    f"get_message_list_from_activity() - Failed to retrieve messages for activity {activity_id}.")
                return InternalErrorResponse("Ocurrió un error interno al obtener los mensajes.").to_response()
        # Convert the QuerySet of Message objects into a list of dictionaries using to_dict()
        message_list_data = [message.to_dict() for message in messages]
        # If the request was successful, return the list of messages
        logger.debug(f"get_message_list() - Successfully retrieved message list: {message_list_data}")
        return SuccessResponse("Successfully retrieved message list.", message_list_data).to_response()  # 200 OK


@require_GET
@csrf_exempt
def api_get_message_list(request):
    """
    API URL: api/messages/list
    API endpoint to get the list of messages.
    """
    # This view only supports GET requests
    _method = 'GET'
    if not request:
        return _method
    if request.method == 'GET':
        # Get the list of messages from the database
        messages, code = get_messages()

        if code == 404:
            # No messages found (get_messages returns 404 if no messages)
            logger.info("get_message_list() - No messages found. Returning empty list.")
            # Return a SuccessResponse with an empty list in the 'data' field
            return SuccessResponse(messages, []).to_response()
        elif code != 200:
            logger.error(f"get_message_list() - Failed to retrieve message list.")
            return InternalErrorResponse(messages).to_response()

        # Convert the QuerySet of Message objects into a list of dictionaries using to_dict()
        message_list_data = [message.to_dict() for message in messages]

        # If the request was successful, return the list of messages
        logger.debug(f"get_message_list() - Successfully retrieved message list: {message_list_data}")
        return SuccessResponse("Successfully retrieved message list.", message_list_data).to_response()

    return None


# Endpoint to create a message
@require_POST
@csrf_protect
@login_required
def api_create_message(request):
    """
    API URL: api/messages/create
    API endpoint to create a new message.
    Requires authentication and CSRF token.
    Expects JSON body with 'message_title' and 'message_description'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the message data from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"create_message() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("create_message() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the message data from the JSON body
        expected_fields = ['body', 'activity_id']
        for key in expected_fields:
            if key not in data:
                logger.error(f"create_message() - Missing '{key}' in request data.")
                return BadRequestResponse(f"Missing '{key}' in request data.").to_response()

        # Create parameters variable with the available fields in the request
        parameters = {}
        for key in data.keys():
            if key in expected_fields:
                parameters[key] = data[key]
        # parameters['user_id'] = 3 # Faking the user for testing purposes
        parameters['user_id'] = request.user.id  # TODO Get the currently authenticated user

        # Create the message in the database
        message, code = create_message(parameters)
        if code != 201:
            logger.error(f"create_message() - Failed to create message.")
            return InternalErrorResponse(message).to_response()
        # Convert datetime fields to the local time zone
        message.created = timezone.localtime(message.created)
        message.updated = timezone.localtime(message.updated)
        # Convert the Message object into a dictionary using to_dict()
        message_data = message.to_dict()
        # If the request was successful, return the message data
        logger.debug(f"create_message() - Successfully created message data: {message_data}")
        return SuccessResponse("Successfully created message data.", message_data).to_response()


# Endpoint to update a message given the id and the parameters
@require_POST
@csrf_protect
@login_required
def api_update_message(request):
    """
    API URL: api/messages/update
    API endpoint to update a message by its ID.
    Receives JSON data with 'message_id', 'message_title', and 'message_description'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the message data from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"update_message_by_id() - Received data: {data}")
            # Get the expected fields
            expected_fields = ['message_id', 'body']
            # Check if the message_id is present in the request
            for key in expected_fields:
                if key not in data:
                    logger.error(f"update_message_by_id() - Missing '{key}' in request data.")
                    return BadRequestResponse(f"Missing '{key}' in request data.").to_response()
            # Create parameters variable with the available fields in the request
            parameters = {}
            for key in data.keys():
                if key in expected_fields:
                    parameters[key] = data[key]
            # Update the message in the database
            message, code = update_message(parameters)
            if code != 200:
                logger.error(f"update_message_by_id() - Failed to update message with ID {parameters['message_id']}.")
                return BadRequestResponse(message).to_response()
            # Convert the Message object into a dictionary using to_dict()
            message_data = message.to_dict()
            # If the request was successful, return the message data
            logger.debug(f"update_message_by_id() - Successfully updated message data: {message_data}")
            return SuccessResponse("Successfully updated message data.", message_data).to_response()

        except json.JSONDecodeError:
            logger.error("update_message_by_id() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()


# Endpoint to delete a message given the id
@require_POST
@csrf_protect
@login_required
def api_delete_message(request):
    """
    API URL: api/messages/delete
    API endpoint to delete a message by its ID.
    Receives JSON data with 'message_id'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the message_id from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"delete_message_by_id() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("delete_message_by_id() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the message_id from the JSON body
        message_id = data.get('message_id')

        # Validate the presence of message_id
        response, code = check_None_API(message_id,
                                        "delete_message_by_id() - Missing 'message' in request data.")
        if code != 200:
            return response

        # Delete the message from the database
        message, code = delete_message_by_id(message_id)
        if code != 200:
            logger.error(f"delete_message_by_id() - Failed to delete message with ID {message_id}.")
            return InternalErrorResponse(message).to_response()
        logger.debug(f"delete_message_by_id() - Successfully deleted message with ID: {message_id}")
        return SuccessResponse(f"Successfully deleted message with ID: {message_id}").to_response()


# ---- User API ----
@require_GET
@csrf_exempt  # TODO Remove this decorator on production
def api_get_user_list(request):
    """
    API URL: api/users/list
    API endpoint to get the list of users.
    """
    # This view only supports GET requests
    _method = 'GET'
    if not request:
        return _method
    if request.method == 'GET':
        # Get the list of users from the database
        users, code = get_users()
        if code != 200:
            logger.error(f"get_user_list() - Failed to retrieve user list.")
            return InternalErrorResponse("Failed to retrieve user list.").to_response()

        # Convert the QuerySet of User objects into a list of dictionaries using to_dict()
        user_list_data = [user_to_dict(user) for user in users]

        # If the request was successful, return the list of users
        logger.debug(f"get_user_list() - Successfully retrieved user list: {user_list_data}")
        return SuccessResponse("Successfully retrieved user list.", user_list_data).to_response()


# Endpoint to get a user by its ID
@require_POST
@csrf_exempt  # TODO Remove this decorator on production
def api_get_user_by_id(request):
    """
    API URL: api/users
    API endpoint to get a user by its ID.
    Receives JSON data with 'user_id'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the user_id from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"get_user_by_id() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("get_user_by_id() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the user_id from the JSON body
        user_id = data.get('user_id')
        if not isinstance(user_id, int):
            logger.error("get_user_by_id() - Invalid user_id format received.")
            return ErrorResponse("Invalid user_id format received.").to_response()

        # Get the user from the database
        user, code = get_user_by_id(user_id)
        if code != 200:
            logger.error(f"get_user_by_id() - Failed to retrieve user with ID {user_id}.")
            return InternalErrorResponse(user).to_response()
        # Convert the User object into a dictionary using to_dict()
        user_data = user_to_dict(user)
        # If the request was successful, return the user data
        logger.debug(f"get_user_by_id() - Successfully retrieved activity data: {user_data}")
        return SuccessResponse("Successfully retrieved activity data.", user_data).to_response()


# Endpoint to update a user given the id and the parameters
@require_POST
@csrf_exempt  # TODO Remove this decorator on production
def api_update_user(request):
    """
    API URL: api/users/update
    API endpoint to update a user by its ID.
    Receives JSON data with 'user_id', 'first_name', and 'last_name', 'username', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the user data from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"update_user_by_id() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("update_user_by_id() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Check required fields
        if 'user_id' not in data:
            logger.error("update_user_by_id() - Missing 'user_id' in request data.")
            return BadRequestResponse("Missing 'user_id' in request data.").to_response()

        # Optional fields to be updated
        expected_types = {
            'user_id': int,
            'username': str,
            'first_name': str,
            'last_name': str,
            'email': str,
            'is_active': bool,
            'is_staff': bool,
            'is_superuser': bool,
            'groups': list,
            'user_permissions': list,
        }

        # Add to parameters variable the available fields in the request
        parameters = {}
        for key, expected_type in expected_types.items():
            if key in data:
                if isinstance(data[key], expected_type):
                    parameters[key] = data[key]

        # Update the user in the database
        user, code = update_user(parameters['user_id'], parameters)
        if code != 200:
            logger.error(f"update_user_by_id() - Failed to update user with ID {parameters['user_id']}.")
            return InternalErrorResponse(user).to_response()
        # Convert the User object into a dictionary using to_dict()
        user_data = user_to_dict(user)
        # If the request was successful, return the user data
        logger.debug(f"update_user_by_id() - Successfully updated user data: {user_data}")
        return SuccessResponse("Successfully updated user data.", user_data).to_response()


# ---- Client API ----
@require_GET
@csrf_exempt  # TODO Remove this decorator on production
def api_get_client_list(request):
    """
    API URL: api/clients/list
    API endpoint to get the list of clients.
    """
    # This view only supports GET requests
    _method = 'GET'
    if not request:
        return _method
    if request.method == 'GET':
        # Get the list of clients from the database
        # clients, code = get_clients_by_user(request.user) # On production, get user from request
        print(request.GET)
        clients, code = get_clients_by_user(int(request.GET['user_id']))
        if code != 200:
            logger.error(f"get_client_list() - Failed to retrieve client list.")
            return InternalErrorResponse(clients).to_response()

        # Convert the QuerySet of Client objects into a list of dictionaries using to_dict()
        client_list_data = [client.to_dict() for client in clients]

        # If the request was successful, return the list of clients
        logger.debug(f"get_client_list() - Successfully retrieved client list: {client_list_data}")
        return SuccessResponse("Successfully retrieved client list.", client_list_data).to_response()


# Endpoint to get a client by its ID
@require_POST
@csrf_exempt  # TODO Remove this decorator on production
def api_get_client_by_id(request):
    """
    API URL: api/clients
    API endpoint to get a client by its ID.
    Receives JSON data with 'client_id'.
    """
    # This view only supports POST requests
    _method = 'POST'
    if not request:
        return _method
    if request.method == 'POST':
        # Get the client_id from the request JSON body
        try:
            data = json.loads(request.body)
            logger.debug(f"get_client_by_id() - Received data: {data}")
        except json.JSONDecodeError:
            logger.error("get_client_by_id() - Invalid JSON format received.")
            return ErrorResponse("Invalid JSON format received.").to_response()

        # Get the client_id from the JSON body
        client_id = data.get('client_id')
        if not isinstance(client_id, int):
            logger.error("get_client_by_id() - Invalid client_id format received.")
            return ErrorResponse("Invalid client_id format received.").to_response()

        # Get the client from the database
        client, code = get_client_by_id(client_id)
        if code != 200:
            logger.error(f"get_client_by_id() - Failed to retrieve client with ID {client_id}.")
            return InternalErrorResponse(client).to_response()
        # Convert the Client object into a dictionary using to_dict()
        client_data = client.to_dict()
        # If the request was successful, return the client data
        logger.debug(f"get_client_by_id() - Successfully retrieved activity data: {client_data}")
        return SuccessResponse("Successfully retrieved activity data.", client_data).to_response()
