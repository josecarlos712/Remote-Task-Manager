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
from .utils.commands_utils import update_commands_list
from .utils.programs_utils import update_programs_list
from .utils.APIResponse import (
    SuccessResponse,
    BadMethodErrorResponse,
    InternalErrorResponse,
    NotFoundResponse,
    ErrorResponse,
    ForbiddenErrorResponse, ValidationErrorResponse, UnauthorizedResponse, check_None_API,
)
from .models import Command, Client, UserSettings

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from .utils.utils import check_None, send_client_get_request, send_client_post_request

# Dict to store avalilable and loaded commands to avoid DB queries.
logger = logging.getLogger(__name__)


# @csrf_protect
# @require_POST
# def api_data(request):
#     _method = 'POST'
#     # If the request is None, the function returns if the function is 'GET' or 'POST'
#     if not request:
#         return _method
#
#     if request.method == "POST":
#         try:
#             data: json = json.loads(request.body)
#             # keyword = data.get("keyword")
#
#             # Buscar la función asociada al keyword en el diccionario
#             api_function: APIFunction = api_functions.get(data['keyword'])
#
#             if api_function:
#                 # Llamar a la función correspondiente
#                 result = api_function.send_request()  # Ejecutar send_request() del objeto APIFunction
#                 return JsonResponse(result)
#             else:
#                 return JsonResponse({"error": "Invalid keyword."}, status=400)
#
#         except json.JSONDecodeError:
#             return JsonResponse({"error": "Invalid JSON."}, status=400)
#     else:
#         return JsonResponse({"error": "Method not allowed."}, status=405)

# ---- Command API ----
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
    check_None_API(client_id, "api_update_commands_list() - Missing 'client_id' in request data.")

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

    # Use the is_user_allowed method of the Client model
    if not client_obj.is_user_allowed(user):
        logger.debug(
            f"api_update_commands_list() - User '{user.username}' is not allowed to access client {client_obj}.")
        # If the user is allowed, return a success response
        return UnauthorizedResponse(f"{user} is not allowed to access {client_obj}.").to_response()  # 200 OK

    # --- Update the commands list for the client ---
    # Get the list of commands from the database
    logger.debug(f"api_update_commands_list() - Fetching command list for client {client_obj}.")

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
    if not client_id:
        logger.warning("api_command() - Missing 'client_id' in request data.")
        api_response = ErrorResponse(message="Falta el ID del cliente.")
        return JsonResponse(api_response.to_dict(), status=400)

    if not command_id:
        logger.warning("api_command() - Missing 'command_id' in request data.")
        api_response = ErrorResponse(message="Falta el ID del comando.")
        return JsonResponse(api_response.to_dict(), status=400)

    # Basic type checks for args and kwargs
    if not isinstance(args, list):
        logger.warning(f"api_command() - 'args' field is not a list: {args}")
        api_response = ErrorResponse(message="'args' debe ser una lista.")
        return JsonResponse(api_response.to_dict(), status=400)

    if not isinstance(kwargs, dict):
        logger.warning(f"api_command() - 'kwargs' field is not a dictionary: {kwargs}")
        api_response = ErrorResponse(message="'kwargs' debe ser un diccionario.")
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


@login_required
@csrf_protect
@require_POST
def refresh_processes_status(request):
    _method = 'GET'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    try:
        # Parse the incoming JSON data
        data = json.loads(request.body)

        # Access data from the parsed JSON
        processes_status = dict(zip(data.get('keys'), data.get('values')))
        print(processes_status)

        # Server side, processes status refresh

        data = {
            'message': f'{processes_status}',
            'status': 'success'
        }
        return JsonResponse(data, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


# ---- User Registration and Authentication API ----
@csrf_protect
@require_POST
def api_register(request):
    """
        Handles user registration via API.
        Receives JSON data, validates it, creates a new user, and logs them in.
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


@require_POST
def get_user_from_token(request):
    """
    Retrieves the user associated with the provided token from the JSON body.

    Args:
        request: The Django request object. It should contain a JSON body with a 'token' field.

    Returns:
        The User object if a valid token is provided, None otherwise.
    """
    _method = 'POST'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    try:
        data = json.loads(request.body)
        token_key = data.get('token')  # Assuming the token field is named "token"

        if token_key:
            try:
                token = Token.objects.get(key=token_key)
                return token.user
            except Token.DoesNotExist:
                return None
        else:
            return None  # Token not provided in JSON
    except json.JSONDecodeError:
        return None  # Invalid JSON
