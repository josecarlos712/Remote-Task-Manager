# Blueprint for modular API routes
from flask import jsonify

from utils.APIResponse import error_handler, APIResponse
from utils import APIResponse


def register(app, path) -> int:
    methods = ['POST']

    app.add_url_rule(
        f'/{path}',
        endpoint=path,
        view_func=error_handler(handler),  # Added error handling
        methods=methods
    )

    #Successful import
    return 0

# Paralelizar el envio del mensaje ya que la interfaz se queda esperando a la recepcion. (utilidad de envio de API)
def handler() -> APIResponse:
    from flask import request, jsonify
    import tkinter as tk
    from tkinter import messagebox

    # Obtener el mensaje del cuerpo de la solicitud POST
    data = request.get_json()
    message = data.get("message", "Default message")

    # Crear la ventana principal
    root = tk.Tk()
    root.title("Message Window")
    root.geometry("100x100")
    root.resizable(False, False)

    # Función para mostrar el mensaje
    def show_message():
        messagebox.showinfo("Message", message)
        root.destroy()

    # Crear botón y mensaje de advertencia
    message_warn_text = tk.Message(text="You received a message!")
    button = tk.Button(root, text="Show Message", command=show_message)
    message_warn_text.pack()
    button.pack(pady=20)

    # Iniciar el bucle de eventos de la interfaz gráfica
    root.mainloop()

    return jsonify(APIResponse.SuccessResponse("Message delivered successfully").to_dict()), 200



