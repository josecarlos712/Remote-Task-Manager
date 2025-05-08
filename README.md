# **Remote-Task-Manager v0.3.0**

Remote Task Manager v0.1.0. Basic web interface
Remote Task Manager v0.2.0. Adding different capabilities to the server.
Remote Task Manager v0.3.0. Loging, logout, register functionality.
Remote Task Manager v0.4.0. Creating the commands system.
Remote Task Manager v0.4.1. Creating the commands system. Adjusting models. 


This is a compilation of utilities to manage your own PC using a Web UI to send commands and run tasks.


## **Capabilities**

**NEW:** Creating the commands system.

**Adjusting models.** Adjusting the models to be more flexible and to be able to add new commands.

## **New version: v0.4.1**
Commands Feature
The application includes a robust system for managing and executing commands on remote clients. This feature allows authenticated and authorized users to trigger specific actions on connected client machines via the web interface.

Key components of the Commands feature include:

Command Model: Defines the structure for individual commands available for execution. Each Command is linked to a specific Client and has a unique command_id within that client. It stores metadata like name, description, the Python handler path for server-side logic (though execution is forwarded), and expected args (as a JSON list).

Client Model: Represents a remote client machine. Each Client has a unique local_ip and port. It is associated with a main_user (nullable) and a ManyToManyField (allowed_users) to specify which additional users have permission to access and execute commands on this client.

UserSettings Model: Linked to the User model via a OneToOneField, this model stores user-specific settings. Crucially for commands, it holds a JSONField (client_api_keys) which stores a dictionary mapping client IPs to the secret API keys required to authenticate requests sent from the server to the client application.

/api/command/execute/ Endpoint: This Django API view handles incoming requests to execute a command. It performs the following steps:

Authenticates the user (@login_required).

Validates the incoming JSON data (requires client_id, command_id, and optionally args/kwargs).

Retrieves the specified Client object from the database.

Checks if the requesting user is allowed to access the retrieved client using the Client.is_user_allowed() method.

Retrieves the secret API key for the target client from the user's UserSettings.

Constructs an outgoing HTTP POST request to the client application's API endpoint (http://<client_ip>:<client_port>/api/command/execute/).

Includes the command_id, args, kwargs, and importantly, the secret API key in a custom header (e.g., X-Client-API-Key) in the outgoing request.

Forwards the response received from the client application back to the original web client.

Includes comprehensive error handling for invalid requests, permission issues, client not found, and communication errors with the client application (timeouts, connection errors, client-side errors).

This architecture ensures that command execution requests are authenticated, authorized based on user-to-client permissions, and securely forwarded to the correct client application using a shared secret API key for validation on the client side.

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