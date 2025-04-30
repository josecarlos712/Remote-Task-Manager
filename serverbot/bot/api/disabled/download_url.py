import os
import time

import requests
from flask import request, jsonify
from urllib.parse import urlparse, unquote
from pathlib import Path
from config import LogLevel, logger
from utils.APIResponse import error_handler, ErrorResponse, SuccessResponse
from utils.endpoints_loader import load_endpoints


def register(app, path):
    methods = ['POST']  # Use POST as we are sending data in the request body

    app.add_url_rule(
        f'/{path}',
        endpoint=path,
        view_func=error_handler(handler),  # Use the handler function defined above
        methods=methods
    )

    # Only the endpoint.py file can register new endpoints
    if Path(__file__).name == "endpoint.py":
        load_endpoints(app, relative_path=path)

    return 0  # Successful import


def download_file(url: str, save_path: str) -> dict:
    try:
        # Send GET request with streaming enabled
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise error for bad responses

        # Get total file size (if available)
        total_size = int(response.headers.get("Content-Length", 0))
        chunk_size = 8192  # 8 KB per chunk
        downloaded_size = 0
        start_time = time.time()

        # Ensure the save directory exists
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    file.write(chunk)
                    downloaded_size += len(chunk)

                    # Calculate progress and speed
                    elapsed_time = time.time() - start_time
                    speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0
                    percentage = (downloaded_size / total_size) * 100 if total_size > 0 else 0

                    # Print progress
                    print(f"\rDownloaded: {downloaded_size}/{total_size} bytes "
                          f"({percentage:.2f}%) | Speed: {speed / 1024:.2f} KB/s", end="")

        print("\nDownload completed successfully!")
        return {"status": "success", "file_path": str(save_path)}

    except requests.exceptions.RequestException as e:
        return {"error": f"Error downloading file: {str(e)}"}


def get_file_metadata(url: str) -> dict:
    """Fetch file metadata (filename, size) without downloading the file."""
    try:
        response = requests.head(url, allow_redirects=True)
        response.raise_for_status()

        # Extract filename from Content-Disposition header (if available)
        filename = None
        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition:
            filename_keyword = "filename="
            if filename_keyword in content_disposition:
                filename = content_disposition.split(filename_keyword)[-1].strip().strip('"')

        # Extract filename from URL if Content-Disposition is missing
        if not filename:
            parsed_url = urlparse(url)
            filename = unquote(parsed_url.path.split("/")[-1])  # Decode URL encoding

        # Extract file size (if available)
        file_size = response.headers.get("Content-Length")
        file_size = int(file_size) if file_size else None

        return {"filename": filename, "file_size": file_size}

    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch file metadata: {str(e)}"}


def handler():
    try:
        # Receive and Validate URL from JSON request
        data = request.get_json()
        print(data)
        if not data:
            return ErrorResponse("There is no data in the JSON request.", log_level=LogLevel.ERROR).to_dict(), 400
        if not 'url' in data and not 'message' in data:
            return ErrorResponse("URL is required in the JSON request.", log_level=LogLevel.ERROR).to_dict(), 400
        url = None
        if 'message' in data:
            url = data['message']
        if 'url' in data:
            url = data['url']

        if not isinstance(url, str):
            return ErrorResponse("Invalid URL format. URL must be a string.", log_level=LogLevel.ERROR).to_dict(), 400

        # Download the file metadata from the URL
        try:
            api_key = "6c5fa4484bb6a55421de4521c8cd4c22"
            api_header = f"?token={api_key}"
            headers = get_file_metadata(url+api_header)
            if "error" in headers:
                return ErrorResponse(headers["error"], log_level=LogLevel.ERROR).to_dict(), 500
            filename = headers.get("filename")
            file_size = headers.get("file_size")
            print(headers)
        except requests.exceptions.RequestException as e:
            return ErrorResponse(f"Error downloading file from URL: {str(e)}", log_level=LogLevel.ERROR).to_dict(), 500

        logger.info(f"Downloading file: {filename} ({file_size * 10 ** (-6)} MB)")

        # Determine the default download directory
        default_downloads_path = Path.home() / "Downloads"  # Cross-platform default Downloads directory
        if not default_downloads_path.exists():
            default_downloads_path.mkdir(parents=True, exist_ok=True)  # Create if it doesn't exist

        # Construct the full file path and save the file
        file_path = default_downloads_path / filename

        # Ensure the file does not already exist (avoid overwriting)
        counter = 1
        while file_path.exists():
            full_filename = f"{filename}_{counter}"
            file_path = default_downloads_path / full_filename
            counter += 1

        try:
            response = download_file(url+api_header, file_path)
        except requests.exceptions.RequestException as e:
            return ErrorResponse(f"Error downloading file from URL: {str(e)}", log_level=LogLevel.ERROR).to_dict(), 500

        # Prepare response data
        file_info = {
            "filename": filename,
            "extension": filename.split('.')[-1],
            "download_directory": str(default_downloads_path),
            "file_path": str(file_path)
        }

        return SuccessResponse("File downloaded successfully.", file_info).to_dict(), 200

    except Exception as e:  # Catch any other unexpected errors
        return ErrorResponse(f"Unexpected error: {str(e)}", log_level=LogLevel.ERROR).to_dict(), 500
