import json
from datetime import datetime

from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from . import urls
from .config.config import logging
from .utils import APIResponse
from .utils.APIResponse import BadMethodErrorResponse, SuccessResponse
from .utils.utils import read_config, sync_programs_from_json
from .utils.api_utils import APIFunction

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
import random

# Diccionario que mapea las claves a las funciones que se deben ejecutar
api_functions = {}


@csrf_protect
@require_POST
def api_data(request):
    _method = 'POST'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    if request.method == "POST":
        try:
            data: json = json.loads(request.body)
            # keyword = data.get("keyword")

            # Buscar la función asociada al keyword en el diccionario
            api_function: APIFunction = api_functions.get(data['keyword'])

            if api_function:
                # Llamar a la función correspondiente
                result = api_function.send_request()  # Ejecutar send_request() del objeto APIFunction
                return JsonResponse(result)
            else:
                return JsonResponse({"error": "Invalid keyword."}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON."}, status=400)
    else:
        return JsonResponse({"error": "Method not allowed."}, status=405)


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
def execute_function(request):
    _method = 'POST'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)  # 400 for malformed JSON

    if not data.get('command'):  # Check if the command is missing
        return JsonResponse({"error": "Missing command."}, status=400)  # 400 for missing command

    command = data.get('command')
    api_function = api_functions.get(command)  # Find the corresponding function

    if not api_function:  # If the function is not found
        return JsonResponse({"error": "Command not found."}, status=404)  # 404 for not found command

    # Call the corresponding API function
    result = api_function.send_request()  # Execute send_request() of the APIFunction
    return JsonResponse(result)


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
