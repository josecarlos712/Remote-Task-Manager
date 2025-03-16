import json
import os
import socket
import subprocess
import requests

from django.db import transaction
from django.http import JsonResponse

from .models import Program

processes = {}
processes_status = {}

url_api_refresh = 'http://192.168.0.3:8000/refresh/'


def send_request_to_client(petition):
    host = '192.168.0.3'
    port = 5000

    try:
        # Create a socket object
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Connect to the client
        client_socket.connect((host, port))

        # Send a request (you may customize this data as needed)
        # _program = Program(program)
        # request = f"{_program.path}"
        request = petition
        print(f"sending {request}")
        client_socket.send(request.encode("utf-8"))

        # Receive response from the client
        response = client_socket.recv(1024)
        print('Received:', response.decode())

        # Close the connection
        client_socket.close()
    except socket.error as e:
        print('Error:', e)


# This function reads all the configuration files and stores it on a dictionary to be readable.
def read_config():
    # Get the current script's directory
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Navigate to the config folder and construct the full path to paths.json
    config_path = os.path.join(current_dir, 'config', 'paths.json')

    try:
        with open(config_path, 'r') as config_file:
            config_data = json.load(config_file)
            print(config_data)
        return config_data
    except FileNotFoundError:
        return f"Configuration file not found: {config_path}"
    except json.JSONDecodeError:
        return "Error decoding JSON from the configuration file: {config_path}"


def is_executable_path(path):
    # TODO
    executable_extensions = ['.exe', '.bat']
    _, extension = os.path.splitext(path)
    return os.path.isfile(path) and extension in executable_extensions


# TO-DO This runs on client-side app. This function must be modified to send a request to the client through API, instead of running the programs straight on the server
def run_program_in_background(program_id, program_path):
    # Get the file extension
    _, ext = os.path.splitext(program_path)

    if ext.lower() == '.exe':
        # If the program is an executable
        process = subprocess.Popen([program_path])
    elif ext.lower() == '.bat':
        # If the program is a batch file
        process = subprocess.Popen([program_path], shell=True)
    else:
        raise ValueError("Unsupported file extension. Only .exe and .bat are allowed.")

    # Store the process in the dictionary with its ID
    if process:
        processes[program_id] = process
    return refresh_processes_status()


def get_process_status(pk):
    process = processes[pk]
    if process:
        # Check if the process is still running
        return process.poll() is None
    return False


def refresh_processes_status():
    for pk, process in processes.items():
        processes_status[pk] = get_process_status(pk)
    endpoint = url_api_refresh + "processes_status/"
    processes_status_serialized = {
        'keys': list(processes_status.keys()),
        'values': list(processes_status.values())
    }
    print(processes_status_serialized)
    response = JsonResponse(processes_status_serialized, status=200)
    response_str = response.content.decode('utf-8')
    response_dict = json.loads(response_str)
    return response_dict


def sync_programs_from_json(json_file_path):
    messages = []
    # Read JSON file
    with open(json_file_path, 'r') as file:
        json_data = json.load(file)

    # Get all programs from the database
    db_programs = Program.objects.all()

    # Track names to determine which programs to keep or delete
    json_program_names = set()
    db_program_names = set(program.name for program in db_programs)

    # Use a transaction for atomicity, either all changes happen or none
    with transaction.atomic():
        # Iterate over the programs in the JSON file
        for json_program in json_data:
            program_name = json_program['name']
            json_program_names.add(program_name)

            # Try to find a matching program in the database by 'name'
            try:
                db_program = Program.objects.get(name=program_name)

                # Check if the existing DB program matches the JSON program using 'is_equal'
                if not db_program.is_equal(json_program):
                    # If the program exists but is different, update it
                    db_program.title = json_program['title']
                    db_program.path = json_program['path']
                    db_program.command = json_program.get('command', 'None')
                    db_program.description = json_program.get('description', 'None')
                    db_program.save()
                    messages.append(f"Program modified. Modifying... {db_program.name}")
                #else:
                    #messages.append(f"Program already exists. Skipping... {db_program.name}")
            except Program.DoesNotExist:
                messages.append(f"Program not exist. Creating... {program_name}")
                # If the program does not exist in the database, create it
                Program.objects.create(
                    name=program_name,
                    title=json_program['title'],
                    path=json_program['path'],
                    command=json_program.get('command', 'None'),
                    description=json_program.get('description', 'None')
                )

        # Find and delete programs in the DB that are not in the JSON
        programs_to_delete = db_program_names - json_program_names
        messages.append(f"Programs to delete: {programs_to_delete if programs_to_delete.__len__()>0 else 'None'}")
        Program.objects.filter(name__in=programs_to_delete).delete()
    return messages


def send_json(endpoint, body):
    # Define the headers (optional, but recommended)
    headers = {
        'Content-Type': 'application/json',  # Define the content type as JSON
        'Accept': 'application/json'
    }

    # Define the payload (data to send in JSON format)
    payload = body
    # {
    #     'key1': 'value1',
    #     'key2': 'value2'
    # }

    # Send the POST request with the JSON data
    response = requests.post(endpoint, headers=headers, json=payload)
