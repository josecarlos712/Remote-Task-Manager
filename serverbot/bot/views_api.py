import json

import requests
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from rest_framework.authtoken.models import Token

from . import urls
import logging
from .utils import APIResponse
from .utils.APIResponse import (
    SuccessResponse,
    BadMethodErrorResponse,
    ValidationErrorResponse,
    InternalErrorResponse,
    BadRequestResponse,
    NotFoundResponse,
    ErrorResponse,
    ForbiddenErrorResponse,
)
from .commands.commands_utils import get_command_by_id
from .models import Command, Client

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

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


@login_required
@csrf_protect
@require_POST
def api_command(request):
    _method = 'POST'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    """
        API URL: /api/command/
        Handles command execution requests via API.
        Requires authentication.
        Receives JSON data with 'client_id', 'command_id', and optional 'args'/'kwargs'.
        Verifies if the requesting user is allowed to access the specified client.
        Forwards the command execution request to the client application's API.
        """
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
    # TODO: Define CLIENT_API_SECRET_KEY in your settings.py
    client_api_key = getattr(settings, 'CLIENT_API_SECRET_KEY', None)

    if not client_api_key:
        logger.error("CLIENT_API_SECRET_KEY is not defined in settings.")
        # Handle this critical configuration error - maybe return a 500 Internal Server Error
        api_response = InternalErrorResponse(message="Server configuration error: Client API key is missing.")
        return JsonResponse(api_response.to_dict(), status=500)

    # --- Forward the command execution request to the Client Application ---
    client_api_url = f"http://{client_obj.local_ip}:{client_obj.port}/{command_endpoint}"

    # Prepare the payload to send to the client application
    client_payload = {
        'command_id': command_id,
        'args': args,
        'kwargs': kwargs,
        # TODO: Include any other necessary data for the client application
        # e.g., user identification if the client needs to know which user initiated the command
        # 'user_id': user.pk,
    }

    # Prepare the headers, including the custom API key header
    # Use a custom header name like 'X-Client-API-Key'
    headers = {
        'Content-Type': 'application/json',
        'X-Client-API-Key': client_api_key  # Add your secret key here
        # TODO: Add any other headers required by the client API
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
                # No need to call user.save() after create_user

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


@csrf_protect
@require_POST
def api_command(request):
    _method = 'POST'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    # Get commands list from the DB
    api_commands = Command.objects.all()
    api_commands_ids = [command.command_id for command in api_commands]
    logger.debug(f"api_command() - Available commands: {api_commands}")

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)  # 400 for malformed JSON

    if not data.get('command_id'):  # Check if the command is missing
        return JsonResponse({"error": "Missing command."}, status=400)  # 400 for missing command

    command = data.get('command_id')
    # TODO: Get the command from the database. If null, do nothing (maybe is an uninplemented command).
    # Checks if the command is in the list of available commands
    if command not in api_commands_ids:
        return JsonResponse({"error": f"api_command() - Command {command} not found."}, status=404)  # 404 for command not found

    # Get the command from the database
    command_obj: Command = get_command_by_id(command)
    if not command_obj:
        return JsonResponse({"error": "api_command() - It could not access to the commands on the DB."}, status=404)

    # Get the arguments from the request
    args = data.get('args', [])  # Default to an empty dictionary if no args are provided

    # Call the command function sending and API request to the client
    # TODO: Send the command to the client

    return JsonResponse({"message": f"Command '{command}' executed successfully."}, status=200)


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


def api_get_tree(request):
    _method = 'GET'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    if request.method == 'GET':
        # This functions gets the api tree from the urls.py variable 'urlpatterns', and gets the method calling the function with the parameter None.
        # It returns a dictionary with the api tree.
        api_tree = {}
        for url in urls.urlpatterns:
            # If the url starts with 'api/', it is an api endpoint
            if url.pattern.regex.pattern.startswith('api/'):
                # Get the method and description of the url
                method = url.callback(request=None)
                api_tree[url.name] = {
                    'description': url.callback.__doc__,
                    'methods': method,
                    'url': url.pattern.regex.pattern,
                }
        print(api_tree)
        return SuccessResponse("API endpoints tree", api_tree).to_dict(), 200
    return BadMethodErrorResponse(request.method, _method).to_dict(), 405
