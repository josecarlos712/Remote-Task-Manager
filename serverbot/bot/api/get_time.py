# Blueprint for modular API routes
from flask import jsonify
from utils.APIResponse import error_handler, APIResponse
from utils import APIResponse

from flask import jsonify
from datetime import datetime


def register(app, path) -> int:
    methods = ['GET']

    app.add_url_rule(
        f'/{path}',
        endpoint=path,
        view_func=error_handler(handler),  # Added error handling
        methods=methods
    )

    return 0


def handler() -> APIResponse:
    # Get the current time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify(APIResponse.SuccessResponse(f"{current_time}").to_dict()), 200
    # Use APIResponse module for returning responses or errors.

