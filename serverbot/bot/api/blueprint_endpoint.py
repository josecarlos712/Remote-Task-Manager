# Blueprint for modular API routes
from pathlib import Path

from flask import jsonify

from utils.APIResponse import error_handler, APIResponse
from utils import APIResponse
from utils.endpoints_loader import load_endpoints


def register(app, path) -> int:
    methods = ['GET']

    app.add_url_rule(
        f'/{path}',
        endpoint=path,
        view_func=error_handler(handler),  # Added error handling
        methods=methods
    )

    # Only the endpoint.py file can register new endpoints
    if Path(__file__).name == "endpoint.py":
        load_endpoints(app, relative_path=path)

    #Successful import
    return 0


def handler() -> APIResponse:
    #Here goes the function to implement
    ...
    # Use APIResponse module for returning responses or errors.
    #   return jsonify(APIResponse.SuccessResponse("This is a success response").to_dict()), 200
