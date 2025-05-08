import requests
from ..models import Client


class APISocket:
    # Example of how to instantiate the class
    # api_function = API_Function(
    #     command="some_command",
    #     description="This is an example API function.",
    #     message_lambda=lambda: {"data": "This is the message content"}  # Lambda for the 'message' field
    # )
    client = 'http://192.168.0.3:5000'

    def __init__(self, clientID):
        # Assign values to parameters
        self.clientID = clientID

    def send_request(self):
        # Create the payload for the API request
        payload = {
            "command": self.command,
            "message": self.message
        }
        # Send the API request to the 'client' endpoint
        response = requests.post(f"{self.client}/api/command", json=payload)
        return response.json()  # Return the response as a JSON

    # Get client socket from DB
    def get_client_socket(self):
        # This function retrieve the client socket from the database
        # Get the client given the clientID
        client = Client.objects.get(id=self.clientID)
        if client:
            # If the client exists, get the IP address and port
            ip_address = client.local_ip
            port = client.port
            # Construct the socket address
            socket_address = f"http://{ip_address}:{port}"
            return socket_address

    def __str__(self):
        return self.description
