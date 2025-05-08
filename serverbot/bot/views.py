import json
import os
import threading

from django.conf import settings
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, Http404, JsonResponse
from django.utils import timezone
from django.utils.timezone import localtime, now
from django.views.decorators.http import require_POST

import logging
from .models import *
from . import utils
from .config import config


# Create your views here.
def login_view(request):
    # Handle GET request (e.g., display the login form)
    return render(request, 'bot/login.html')


def homePage(request):
    activities = Activity.objects.all()
    programs = Program.objects.all()

    # Ruta del directorio donde están los componentes
    components_dir = os.path.join(settings.BASE_DIR, 'bot', 'templates', 'bot', 'dynamic_components')
    # Obtener la lista de archivos HTML en el directorio
    components = [f for f in os.listdir(components_dir) if f.endswith('.html')]

    # If it's the first time the server is loaded, we need to do some initialization
    if config.SERVER_INITIALIZATION:
        status, message = config.configuration.initialize_server()
        if status:
            # If the server was initialized successfully, we can set the SERVER_INITIALIZATION to False
            config.SERVER_INITIALIZATION = False
        else:
            # If the server was not initialized successfully, we can return an error page
            context = {'error': message}
            return error_page_view(request, context['error'])
    # If the server was initialized successfully, we can render the home page
    context = {'activities': activities, 'programs': programs, 'dynamic_components': components}
    return render(request, 'bot/home.html', context)


def error_page_view(request, error_message=None):
    """
    Renders a generic error page.

    Args:
        request: The Django HttpRequest object.
        error_message (str, optional): A specific error message to display.
                                       Defaults to None.
    """
    context = {}
    if error_message:
        context['error'] = error_message
    else:
        # Provide a default message if none is passed
        context['error'] = "An unexpected error occurred."

    return render(request, 'bot/error.html', context)


def activity_page(request, pk):
    activity = Activity.objects.get(id=pk)

    context = {'activity': activity}
    return render(request, 'bot/activity.html', context)


def room_page(request, pk):
    room = Room.objects.get(id=pk)
    room_messages = room.message_set.all()

    context = {'room': room, 'room_messages': room_messages}
    return render(request, 'bot/room.html', context)


def cooking(request):
    return render(request, 'bot/cooking.html')


def load_program(request, pk):
    try:
        program = get_object_or_404(Program, pk=pk)
        exists = utils.is_executable_path(program.path)
        if exists:
            context = {'message': 'The .exe file exists.', 'path': program.path, 'error': False}
            # run_program_in_background returns a JsonResponse with the current status of every program
            return utils.run_program_in_background(pk, program.path)
        else:
            context = {'message': 'The .exe file does not exist.', 'path': program.path, 'error': True}
    except Http404:
        context = {'message': 'Program not found.', 'path': "Null", 'error': True}
        return render(request, 'bot/error.html', context=context)

    if context['error']:
        return render(request, 'bot/error.html', context=context)


def error_page():
    return None


def component_programs_view(request):
    programs = Program.objects.all()
    # utils.send_request_to_client(path)
    programs_state = utils.refresh_processes_status()
    now_str = localtime(timezone.now()).strftime("%H:%M:%S")
    print(f"now: {now_str}, programs: {len(programs_state['keys']) > 0}")
    context = {'programs': programs, 'now_date': now_str, 'programs_state': programs_state}
    return render(request, 'bot/component_program.html', context=context)


def commponent_commands_view(request):
    """
    Retrieves all Command objects from the database and renders the
    component_command.html template with the commands in the context.
    """
    try:
        # Get all Command objects from the database
        commands = Command.objects.all()

        # Prepare the context dictionary
        context = {
            'commands': commands
        }

        # Render the template with the commands in the context
        return render(request, 'bot/component_command.html', context)

    except Exception as e:
        # TODO: Implement more specific error handling if needed (e.g., Command model not found)
        print(f"An error occurred while fetching commands: {e}") # Log the error for debugging
        # You might want to render an error template or return an error response
        # For now, we'll just print the error and render an empty template or similar
        # Returning an empty context might be acceptable if the template handles empty lists
        return render(request, 'bot/component_command.html', {'commands': []}) # Render with empty list on error


def about_view(request):
    return render(request, 'bot/about.html', context={})


def register_view(request):
    return render(request, 'bot/register.html', context={})
