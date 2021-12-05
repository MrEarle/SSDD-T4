from abc import abstractmethod
from typing import Callable, Dict, Tuple, Union

from socketio import Server


class Middleware:
    def __init__(self, socketio: Server, next_middleware=None, main_server=None):

        # El objeto Server del socketio
        self.socketio = socketio

        # El siguiente middleware
        self.next_middleware = next_middleware

        # La clase definida en src/server/main.py
        self.main_server = main_server

        # ! ESTO ES NECESARIO DEFINIRLO EN LA CLASE HIJA
        # Handlers es un diccionario que contiene los handlers de los eventos
        # Toda subclase de Middleware debe definir esta propiedad
        # El formato que debe tener es:
        # {
        #     'event_name': lambda sid, data: True, {...}
        # }
        #
        # Hay 3 posibles valores de retorno del handler:
        # 1. bool, dict:
        #     bool: True si se debe pasar el evento al siguiente middleware
        #     dict: Diccionario con los datos a enviar de vuelta al cliente
        # 2. dict:
        #     Si se devuelve solo un diccionario, se asume que el bool es True, y se pasa el mensaje al siguiente middleware
        #     dict: Diccionario con los datos a enviar de vuelta al cliente
        # 3. None:
        #     Si se devuelve None, se asume que el bool es True, y se pasa el mensaje al siguiente middleware
        #     Ademas, se asume que el diccionario es vacio
        self.handlers: Dict[str, Callable[[str, dict], Union[Tuple[bool, dict], dict, None]]] = {}

    def set_next(self, middleware):
        """Funcion para setear el siguiente middleware"""
        self.next_middleware = middleware

    def handle(self, event: str, sid: str, data: dict) -> dict:
        """Handle the event.

        Args:
            event (str): The event name.
            sid (str): The session id.
            data (dict): The data passed to the event.

        Returns:
            dict: Data to be sent back to the client.
        """
        # Si el evento esta en el diccionario de handlers, se ejecuta el handler
        pass_next, ret_val = self.__handle(event, sid, data)

        # Si pass_next es True y hay un siguiente middleware, se ejecuta el siguiente middleware
        if pass_next and self.next_middleware:
            # Ejecutar el siguiente middleware
            next_ret_val = self.next_middleware.handle(event, sid, data)

            # Actualizar el diccionario de retorno con los datos del siguiente middleware
            if next_ret_val:
                ret_val.update(next_ret_val)

        # Se retorna el diccionario de retorno, que se le enviará como respuesta al cliente
        return ret_val

    def __handle(self, event: str, sid: str, data: dict) -> Tuple[bool, dict]:
        """Handle the event.

        Args:
            event (str): The event name.
            sid (str): The session id.
            data (dict): The data passed to the event.

        Returns:
            bool: Whether to pass the event to the next middleware.
            dict: Data to be sent back to the client.
        """

        # Se obtiene el handler del evento y se ejecuta
        handler = self.get_handler(event)
        handler_result = handler(sid, data)

        if isinstance(handler_result, tuple):
            # Si el handler devuelve una tupla (bool, dict), se retorna esa tupla
            return handler_result
        elif isinstance(handler_result, dict):
            # Si el handler devuelve un diccionario, se retorna (True, dict)
            return True, handler_result
        else:
            # Si el handler devuelve None, se retorna (True, {})
            return True, {}

    def get_handler(self, event: str) -> Callable[[str, dict], Union[Tuple[bool, dict], dict, None]]:
        """Get the handler for the event.

        Args:
            event (str): The event name.

        Returns:
            callable: The handler for the event.
        """

        # Si el evento esta en el diccionario de handlers, se retorna el handler
        if event in self.handlers:
            return self.handlers[event]

        # Si no esta en el diccionario, se retorna el handler por defecto que no hace nada
        return lambda *args, **kwargs: None
