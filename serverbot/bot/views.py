import os
import threading

from django.conf import settings
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, Http404, JsonResponse
from django.utils import timezone
from django.utils.timezone import localtime, now

from .models import *
from . import utils

import subprocess


# Create your views here.
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect to a success page, such as the user's dashboard
            return redirect('home')  # Change 'dashboard' to the name of your dashboard URL pattern
        else:
            # Handle invalid login credentials (e.g., display an error message)
            return render(request, 'bot/login.html', {'error': 'Invalid username or password'})
    else:
        # Handle GET request (e.g., display the login form)
        return render(request, 'bot/login.html')


def logout_view(request):
    logout(request)
    # Redirect to a desired page after logging out
    return redirect('home')  # Redirect to the login page after logging out


def homePage(request):
    activities = Activity.objects.all()
    programs = Program.objects.all()

    # Ruta del directorio donde están los componentes
    components_dir = os.path.join(settings.BASE_DIR, 'bot', 'templates', 'bot', 'dynamic_components')
    # Obtener la lista de archivos HTML en el directorio
    components = [f for f in os.listdir(components_dir) if f.endswith('.html')]
    print(components)
    context = {'activities': activities, 'programs': programs, 'dynamic_components': components}
    return render(request, 'bot/home.html', context)


def activity_page(request, pk):
    activity = Activity.objects.get(id=pk)
    programs = activity.program_set.all()

    context = {'activity': activity, 'programs': programs}
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
    #utils.send_request_to_client(path)
    programs_state = utils.refresh_processes_status()
    now_str = localtime(timezone.now()).strftime("%H:%M:%S")
    print(f"now: {now_str}, programs: {len(programs_state['keys']) > 0}")
    context = {'programs': programs, 'now_date': now_str, 'programs_state': programs_state}
    return render(request, 'bot/component_program.html', context=context)
