# Remote Task Server

This project corresponds to the **server** component of a client-server system developed as a Bachelor's Thesis (TFG). It allows managing and controlling multiple clients on a local network through a web interface, remote commands, and real-time notifications.

You can find the client-side application on https://github.com/josecarlos712/Remote-Task-Manager-Client

## 🧩 Key Features

- Responsive web interface (HTML, CSS, JS with AJAX).
- Python backend using Flask.
- Dynamic and modular endpoint loading via recursive structure.
- User authentication system.
- Structured API with unified error handling (`APIResponse`).
- Communication with a Telegram bot for remote control.

## 📂 Project Structure

```

remote-task-server/
├── api/                # Hierarchical endpoints
│   └── ...             # Each endpoint is an independent file
├── static/             # Web resources (JS, CSS, etc.)
├── templates/          # HTML templates
├── websocket/          # WebSocket connection management
├── main.py             # Server entry point
├── auth.py             # Authentication module
└── utils/              # Auxiliary functions

````

## 🚀 Running the Project

1. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
````

2. Run the server:

```bash
python main.py
```

Access the API interface at `http://localhost:5000`.

## ⚙️ Main Dependencies

* Flask
* Requests

## 🔐 Security

* Access is restricted via login.
* CSRF protection pending implementation.
* API input validation in progress.

## 📌 Development Status

✅ Modular endpoint system
✅ Basic authentication
❌ WebSocket communication
❌ API input validation and automated testing
❌ HTTPS support
❌ Advanced user management
❌ API Keys for serveless usage

## 📄 License

MIT License