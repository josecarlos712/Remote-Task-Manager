import json
import requests
from datetime import datetime
from .utils import read_config, sync_programs_from_json
from .utils_api import APIFunction

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
    if request.method == "POST":
        try:
            data: json = json.loads(request.body)
            #keyword = data.get("keyword")

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
def execute_function(request):
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


def button1_function():
    messages = sync_programs_from_json("bot/config/programs.json")
    return {"message": "<br>".join(messages)}


def button2_function():
    config = read_config()
    if config:
        return {"message": config['file_extensions']['images'].__str__()}
    else:
        return {"message": "Fail loading config."}


# API Functions
def dice():
    return {"message": f"Random number: {random.randint(1, 100)}"}


def button4_function():
    # delete button
    return {"message": "\n\n\n"}


def test_page(request):
    if request.method == "POST":
        time = datetime.now()
        # Render the HTML template
        html_content = render(request, 'bot/test_page.html', context={"time": time})
        return HttpResponse(html_content, content_type='text/html')
    else:
        return HttpResponse(status=405)  # Method Not Allowed


def setup():
    # APIFuntion definitions
    # Show popup
    api_functions['popup'] = APIFunction(command="popup",
                                         description="This is an example API function.",
                                         message_lambda=lambda: {'message': "Popup message"})
