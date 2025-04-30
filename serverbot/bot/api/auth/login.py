# Blueprint for modular API routes
from flask import jsonify

from utils.APIResponse import error_handler, APIResponse
from utils import APIResponse


def register(app, path) -> int:
    methods = ['GET']

    app.add_url_rule(
        f'/{path}',
        endpoint=path,
        view_func=error_handler(handler),  # Added error handling
        methods=methods
    )

    #Successful import
    return 0


def handler() -> APIResponse:
    #Here goes the function to implement
    ...
    # Use APIResponse module for returning responses or errors.
    #   return jsonify(APIResponse.SuccessResponse("This is a success response").to_dict()), 200


def login():
    """ Authenticate user and issue a token """
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if username == 'admin' and password == 'password':  # Replace with real authentication
        token = os.urandom(16).hex()
        config.login_tokens[token] = username
        return jsonify(APIResponse.SuccessResponse("Login successful", {'token': token}).to_dict()), 200

    return jsonify(APIResponse.ErrorResponse('Invalid credentials').to_dict()), 401