# Blueprint for modular API routes
from pathlib import Path

from flask import jsonify, request

import config
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
    if request.method == 'OPTIONS':
        # Flask-CORS should handle this, but you can explicitly return a response if needed
        return '', 204
    name = config.configuration["domain_name"]
    user = config.configuration["user_name"]
    local_ip = config.configuration["local_ip"]
    port = config.configuration["port"]
    return jsonify(
        APIResponse.SuccessResponse("APIRest is running",
                                    {"client": f"{name}/{user}", "socket": f"{local_ip}:{port}"}).to_dict()
    ), 200
    # Use APIResponse module for returning responses or errors.
    #   return jsonify(APIResponse.SuccessResponse("This is a success response").to_dict()), 200
