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


def logout():
    """ Log out user by invalidating the token """
    data = request.json
    token = data.get('token')
    user = data.get('username')

    if token in config.login_tokens:
        del config.login_tokens[token]
        return jsonify(APIResponse.SuccessResponse('Logged out').to_dict()), 200

    return jsonify(APIResponse.ErrorResponse('Invalid token').to_dict()), 401
