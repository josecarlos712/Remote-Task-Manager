
# Remote-Task-Manager
Remote Task Manager v24.1023.01 This is a compilation of utilities to manage your own PC using a Web UI to send commands and run tasks.

## Capabilities
**NEW:** On the "Programs" section there is a new "Refresh" button. Synchronize the configuration JSON "json_file_path" of the client with the database. Updates the executable programs on the server.

## Function definitions

### sync_programs_from_json(json_file_path)
- **Description**: Read the JSON where the program paths are stored (`json_file_path`). Convert it to a dictionary and update the database (`Program` model) according to the JSON content. The JSON is mirrored in the user's database.
- **4 cases**:
    1. The program exists in the DB and is identical to the definition in the JSON: The entry is skipped.
    2. The program exists in the DB and is different from the definition in the JSON: The DB entry is updated.
    3. The program doesn't exist in the DB but exists in the JSON: It is created in the DB.
    4. The program exists in the DB but doesn't exist in the JSON: It is deleted from the DB.

---

### send_request_to_client(petition)
- **Description**: Sends a request (`petition`) to a client running on the specified host and port. It uses a socket to connect to the client, send the petition, and retrieve a response.
- **Parameters**:
  - `petition` (str): The message or command to send to the client.
- **Returns**: None (prints the response from the client).

---

### read_config()
- **Description**: Reads the configuration file (`paths.json`) located in the `config` folder and returns the data as a dictionary. If the file is not found or there is an issue with the JSON format, an appropriate error message is returned.
- **Returns**: Dictionary with the configuration data or an error message.

---

### is_executable_path(path)
- **Description**: Checks if the provided `path` exists on the system and whether it has a valid executable or batch file extension.
- **Parameters**:
  - `path` (str): The file path to check.
- **Returns**: Boolean (`True` if the path exists and has a valid extension, `False` otherwise).

---

### run_program_in_background(program_id, program_path)
- **Description**: Runs a program (either `.exe` or `.bat`) in the background using the provided `program_path`. The process is stored in a dictionary using `program_id` as the key.
- **Parameters**:
  - `program_id` (int): The unique identifier of the program.
  - `program_path` (str): The path of the executable or batch file.
- **Returns**: Dictionary of process statuses.

---

### check_process_status(pk)
- **Description**: Checks whether a process with the specified `pk` (primary key) is still running.
- **Parameters**:
  - `pk` (int): The identifier of the process to check.
- **Returns**: Boolean (`True` if the process is running, `False` otherwise).

---

### refresh_processes_status()
- **Description**: Iterates over the stored processes and updates their statuses in the `processes_status` dictionary. The statuses are then sent to an API endpoint.
- **Returns**: A JSON response containing the serialized process statuses.

---

### send_json(endpoint, body)
- **Description**: Sends a POST request with a JSON body to a specified API `endpoint`.
- **Parameters**:
  - `endpoint` (str): The API URL where the request is sent.
  - `body` (dict): The JSON payload to send.
- **Returns**: The response from the API (if any).

