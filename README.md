# **Remote-Task-Manager v0.4.3**

Remote Task Manager v0.1.0. Basic web interface
Remote Task Manager v0.2.0. Adding different capabilities to the server.
Remote Task Manager v0.3.0. Loging, logout, register functionality.
Remote Task Manager v0.4.0. Creating the commands system.
Remote Task Manager v0.4.1. Creating the commands system. Adjusting models.
Remote Task Manager v0.4.2. Creating the commands system. Send commands requests.
Remote Task Manager v0.4.3. Creating the program system. Send program requests.


This is a compilation of utilities to manage your own PC using a Web UI to send commands and run tasks.


## **Capabilities**

**NEW:** Creating the programs system.

## **New version: v0.4.3**
Programs Feature
The application includes a system for managing and monitoring programs available on remote clients. This feature allows the server to receive lists of programs from connected clients, maintain a database record of these programs, and track their status (like availability and running state).

Key components of the Programs feature include:

Program Model: Defines the structure for programs discovered on client machines. Each Program is linked to a specific Client and is uniquely identified by its name within that client. It stores metadata such as title, description, available status (whether the client reported it as available), is_running status, and timestamps (created, updated, start_time, end_time).

Client Model: Represents a remote client machine. Each Client has a unique local_ip and port, and is associated with users via main_user and allowed_users. It serves as the link between the server's database records and the actual client machine where programs reside.

update_programs_list Function: This function is responsible for synchronizing the list of programs for a specific client in the database with a list received from the client application. It iterates through the received list, using the sync_program_from_dict helper for individual program creation/updates, and sets programs not in the received list to available=False instead of deleting them.

update_existing_program Function: This function is a helper used by the synchronization process. Its specific role is to find an existing Program object for a given Client and name and update only the fields provided in the input dictionary (program_data). It ensures that programs are only updated if they already exist and handles updating fields like title, description, available, is_running, and timestamps (start_time, end_time). It includes validation for input data types and logs warnings/errors for missing programs or invalid data.

Client API Endpoint (e.g., /api/program/list): The client application is expected to expose an API endpoint (e.g., /api/program/list) that the server can call (likely via a POST request) to retrieve the current list of programs available on that client. This list is then processed by the server's update_programs_list function.

Client API Endpoint (e.g., api/program/status): The client application might also expose an endpoint (e.g., api/program/status) that the server can call to receive periodic updates on the running status of programs. This would trigger the server to call update_existing_program to update the is_running, start_time, and end_time fields for specific programs.

This system allows the server to maintain a dynamic inventory of programs available on connected clients, reflecting their current state based on information received from the clients themselves.


## **Function definitions**

### **sync_programs_from_json(json_file_path)**

- **Description**: Read the JSON where the program paths are stored (json_file_path). Convert it to a dictionary and update the database (Program model) according to the JSON content. The JSON is mirrored in the user's database.
- **4 cases**:
    1. The program exists in the DB and is identical to the definition in the JSON: The entry is skipped.
    2. The program exists in the DB and is different from the definition in the JSON: The DB entry is updated.
    3. The program doesn't exist in the DB but exists in the JSON: It is created in the DB.
    4. The program exists in the DB but doesn't exist in the JSON: It is deleted from the DB.

### **send_request_to_client(petition)**

- **Description**: Sends a request (petition) to a client running on the specified host and port. It uses a socket to connect to the client, send the petition, and retrieve a response.
- **Parameters**:
  - petition (str): The message or command to send to the client.
- **Returns**: None (prints the response from the client).

### **read_config()**

- **Description**: Reads the configuration file (paths.json) located in the config folder and returns the data as a dictionary. If the file is not found or there is an issue with the JSON format, an appropriate error message is returned.
- **Returns**: Dictionary with the configuration data or an error message.

### **is_executable_path(path)**

- **Description**: Checks if the provided path exists on the system and whether it has a valid executable or batch file extension.
- **Parameters**:
  - path (str): The file path to check.
- **Returns**: Boolean (True if the path exists and has a valid extension, False otherwise).

### **run_program_in_background(program_id, program_path)**

- **Description**: Runs a program (either .exe or .bat) in the background using the provided program_path. The process is stored in a dictionary using program_id as the key.
- **Parameters**:
  - program_id (int): The unique identifier of the program.
  - program_path (str): The path of the executable or batch file.
- **Returns**: Dictionary of process statuses.

### **check_process_status(pk)**

- **Description**: Checks whether a process with the specified pk (primary key) is still running.
- **Parameters**:
  - pk (int): The identifier of the process to check.
- **Returns**: Boolean (True if the process is running, False otherwise).

### **refresh_processes_status()**

- **Description**: Iterates over the stored processes and updates their statuses in the processes_status dictionary. The statuses are then sent to an API endpoint.
- **Returns**: A JSON response containing the serialized process statuses.

### **send_json(endpoint, body)**

- **Description**: Sends a POST request with a JSON body to a specified API endpoint.
- **Parameters**:
  - endpoint (str): The API URL where the request is sent.
  - body (dict): The JSON payload to send.
- **Returns**: The response from the API (if any).

### **getCookie(name)**

- **Description**: Retrieves the value of a specific cookie by its name from the browser's document.cookie. Commonly used for fetching the CSRF token.
- **Parameters**:
  - name (string): The name of the cookie to retrieve.
- **Returns**: string | null: The value of the cookie if found, otherwise null.

### **displayErrors(errors)**

- **Description**: Logs validation error messages received from the server to the browser's available error fields inform the user.
- **Parameters**:
  - errors (object | null): An object containing error details, typically with field names as keys and arrays of error messages as values.
- **Returns**: None.

### **sendAjaxPostRequest(url, jsonData)**

- **Description**: A general-purpose function to send an asynchronous POST request to a specified URL with JSON data using XMLHttpRequest. Handles CSRF token inclusion and parses the JSON response.
- **Parameters**:
  - url (string): The API endpoint URL.
  - jsonData (object): The data to send in the request body as a JSON object.
- **Returns**: Promise&lt;\[boolean, object | string\]&gt;: A Promise that resolves with a tuple indicating success status and the response data or error information.

### **validateRegistrationForm()**

- **Description**: Performs client-side validation checks on the registration form input fields (username, email, password, confirm password).
- **Parameters**: None.
- **Returns**: boolean: True if all validation checks pass, False otherwise.

### **isValidEmail(email)**

- **Description**: Checks if a given string conforms to a standard email address format using a regular expression.
- **Parameters**:
  - email (string): The string to validate as an email address.
- **Returns**: boolean: True if the string is a valid email format, False otherwise.

### **sendRegistrationRequestAJAX(registrationData)**

- **Description**: Sends an AJAX POST request to the registration API endpoint (/api/accounts/register) using the sendAjaxPostRequest general function.
- **Parameters**:
  - registrationData (object): An object containing the user registration details (username, email, password, etc.).
- **Returns**: None (handles the response via the sendAjaxPostRequest Promise).

### **sendLoginRequestAJAX(loginData)**

- **Description**: Sends an AJAX POST request to the login API endpoint (/api/accounts/login) using the sendAjaxPostRequest general function.
- **Parameters**:
  - loginData (object): An object containing the user login credentials (username, password).
- **Returns**: None (handles the response via the sendAjaxPostRequest Promise).