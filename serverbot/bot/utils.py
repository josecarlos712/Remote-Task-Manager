import os
import socket
import subprocess

from .models import Program


processes = []
processes_status = []


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


def check_if_path_exists(path):
    # TODO
    executable_extensions = ['.exe', '.bat']
    _, extension = os.path.splitext(path)
    return os.path.isfile(path) and extension in executable_extensions


def run_program_in_background(program_id, program_path):
    # Function to run the external program
    process = subprocess.Popen([program_path])
    processes[program_id] = process


def check_process_status(pk):
    process = processes[pk]
    if process:
        # Check if the process is still running
        return process.poll() is None
    return False


def refresh_processes_status():
    for pk, process in processes:
        processes_status[pk] = check_process_status(pk)
    return processes_status
