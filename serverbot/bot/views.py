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
from .utils import activity_utils, programs_utils, messages_utils, user_utils, commands_utils

import logging
from .models import *
from . import utils
from .config import config


# Create your views here.
def login_view(request):
    # Handle GET request (e.g., display the login form)
    return render(request, 'bot/login.html')


def homePage(request):
    user = request.user
    # Check if the user is authenticated
    if not user.is_authenticated:
        # If the user is not authenticated, user is none
        user = None

    # Ruta del directorio donde están los componentes
    components_dir = os.path.join(settings.BASE_DIR, 'bot', 'templates', 'bot', 'dynamic_components')
    # Obtener la lista de archivos HTML en el directorio
    components = [f for f in os.listdir(components_dir) if f.endswith('.html')]

    context = {'dynamic_components': components, 'user': user}
    if not request.user.is_authenticated:
        # If the user is not authenticated, redirect to the login page
        # Get all Command objects from the database
        commands, code = commands_utils.get_command_list_by_user(request.user.id)
        if code >= 300:
            # Handle the error case, e.g., redirect to an error page or show a message
            return error_page_view(request, f"Commands not found. Error: {commands}")
        # Convert the commands to a list of dictionaries
        commands_list: list[Command] = [command.to_dict() for command in commands]
        # Render the template with the commands in the context
        context.update({'commands': commands_list})

        # Get all Program objects from the database
        programs, code = programs_utils.get_program_list_by_user(request.user.id)
        if code != 200:
            # Handle the error case, e.g., redirect to an error page or show a message
            return error_page_view(request, f"Programs not found. Error: {programs}")
        # Convert the programs to a list of dictionaries
        programs_list = [program.to_dict() for program in programs]
        # Render the template with the programs in the context
        context.update({'programs': programs_list})

    # If it's the first time the server is loaded, we need to do some initialization
    # if config.SERVER_INITIALIZATION:
    #     status, message = config.configuration.initialize_server()
    #     if status:
    #         # If the server was initialized successfully, we can set the SERVER_INITIALIZATION to False
    #         config.SERVER_INITIALIZATION = False
    #     else:
    #         # If the server was not initialized successfully, we can return an error page
    #         context = {'error': message}
    #         return error_page_view(request, context['error'])
    # If the server was initialized successfully, we can render the home page
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


# ---- Activity ----
def activity_page(request, pk):
    pk = int(pk)
    activity, code = activity_utils.get_activity_by_id(pk)
    if code != 200:
        # Handle the error case, e.g., redirect to an error page or show a message
        return error_page_view(request, f"Activity not found. Error: {activity}")
    # Convert the activity to a dictionary
    activity_dict = activity.to_dict()

    messages, code = messages_utils.get_messages_from_activity(pk)
    if code != 200:
        # Handle the error case, e.g., redirect to an error page or show a message
        return error_page_view(request, f"Messages not found. Error: {messages}")
    # Convert the messages to a list of dictionaries
    messages_list = [message.to_dict() for message in messages]

    context = {'activity': activity_dict, 'messages': messages_list}
    return render(request, 'bot/activity.html', context)


def component_activities_view(request):
    """
    Retrieves all Activity objects from the database and renders the 'component_activity.html' template with the activities in the context.
    """
    # Return all activities if the user is not authenticated
    activities, code = activity_utils.get_activities()
    if code != 200:
        # Handle the error case, e.g., redirect to an error page or show a message
        return error_page_view(request, f"Activities not found. Error: {activities}")

    # Convert the activities to a list of dictionaries
    activities_list = [activity.to_dict() for activity in activities]
    #activities_list = []
    # Render the template with the activities in the context
    context = {'activities': activities_list}
    return render(request, 'bot/component_activity.html', context=context)


def create_activity_view(request):
    """
    Renders the 'create_activity.html' template for creating a new activity.
    """
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        # If the user is not authenticated, redirect to the login page
        return redirect('login')

    # Render the template for creating a new activity
    return render(request, 'bot/create_activity.html')


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
    """
    Retrieves all Program objects from the database and renders the 'component_program.html' template with the programs in the context.
    """
    if not request.user.is_authenticated:
        # If the user is not authenticated, redirect to the login page
        return redirect('login')

    # Get all Program objects from the database
    programs, code = programs_utils.get_program_list_by_user(request.user.id)
    if code != 200:
        # Handle the error case, e.g., redirect to an error page or show a message
        return error_page_view(request, f"Programs not found. Error: {programs}")
    # Convert the programs to a list of dictionaries
    programs_list = [program.to_dict() for program in programs]
    # Render the template with the programs in the context
    context = {'programs': programs_list}
    return render(request, 'bot/component_program.html', context=context)


# ---- Commands ----
def component_commands_view(request):
    """
    Retrieves all Command objects from the database and renders the
    component_command.html template with the commands in the context.
    """
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        # If the user is not authenticated, redirect to the login page
        return redirect('login')
    # Sync commands from the user
    # response, code = commands_utils.sync_commands_list(request.user)
    # if code > 200:
    #     # Handle the error case, e.g., redirect to an error page or show a message
    #     return error_page_view(request, f"Error {code} syncing commands: {response}")

    # Get all Command objects from the database
    commands, code = commands_utils.get_command_list_by_user(request.user.id)
    if code >= 300:
        # Handle the error case, e.g., redirect to an error page or show a message
        return error_page_view(request, f"Commands not found. Error: {commands}")
    # Convert the commands to a list of dictionaries
    commands_list: list[Command] = [command.to_dict() for command in commands]
    # Render the template with the commands in the context
    context = {'commands': commands_list}
    return render(request, 'bot/component_command.html', context=context)


def about_view(request):
    return render(request, 'bot/about.html', context={})


def register_view(request):
    return render(request, 'bot/register.html', context={})


# User management views
def user_configuration_view(request, pk=None):
    """
    Renders the user configuration page.
    """
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        # If the user is not authenticated, redirect to the login page
        return redirect('login')

    # Get the current user
    user = request.user
    # If a user ID is provided, get the user by ID
    if not isinstance(pk, int):
        pk = int(pk)

    if pk is not None:
        user, code = user_utils.get_user_by_id(pk)
        if code != 200:
            # Handle the error case, e.g., redirect to an error page or show a message
            return error_page_view(request, f"User not found. Error: {user}")
    if user.id != request.user.id:
        # If the user ID does not match the current user, return an error
        return error_page_view(request, "You do not have permission to access this page.")

    # If the user is authenticated and the user ID matches, render the user configuration template
    # Convert the user to a dictionary
    user_dict = user_to_dict(user)
    context = {'user_data': user_dict}
    return render(request, 'bot/user_configuration.html', context=context)


def user_page():
    return None