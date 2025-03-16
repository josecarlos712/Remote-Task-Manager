import uuid
import requests


class APIFunction:
    # Example of how to instantiate the class
    # api_function = API_Function(
    #     command="some_command",
    #     description="This is an example API function.",
    #     message_lambda=lambda: {"data": "This is the message content"}  # Lambda for the 'message' field
    # )
    client = 'http://192.168.0.3:5000'

    def __init__(self, command, description, message_lambda):
        # Assign values to parameters
        self.command = command
        self.description = description
        self.unique_id = str(uuid.uuid4())  # Generate a unique ID
        # Define the message using the lambda function
        self.message = message_lambda()['message']

    def send_request(self):
        # Create the payload for the API request
        payload = {
            "command": self.command,
            "message": self.message
        }
        # Send the API request to the 'client' endpoint
        response = requests.post(f"{self.client}/api/command", json=payload)
        return response.json()  # Return the response as a JSON

    def __str__(self):
        return self.description


#class APIConfiguration(AppConfig):
