from abc import abstractmethod
from typing import Callable, Dict, Tuple, Union

from socketio import Server


class Middleware:
    def __init__(self, socketio: Server, next_middleware=None, main_server=None):
        self.socketio = socketio
        self.next_middleware = next_middleware
        self.main_server = main_server

        self.handlers: Dict[str, Callable[[str, dict], Union[Tuple[bool, dict], dict, None]]] = {}

    def set_next(self, middleware):
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

        pass_next, ret_val = self.__handle(event, sid, data)
        if pass_next and self.next_middleware:
            next_ret_val = self.next_middleware.handle(event, sid, data)

            # Update the return value if the next middleware returned something
            if next_ret_val:
                ret_val.update(next_ret_val)

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
        handler = self.get_handler(event)
        handler_result = handler(sid, data)

        if isinstance(handler_result, tuple):
            return handler_result
        elif isinstance(handler_result, dict):
            return True, handler_result
        else:
            return True, {}

    def get_handler(self, event: str) -> Callable[[str, dict], Union[Tuple[bool, dict], dict, None]]:
        """Get the handler for the event.

        Args:
            event (str): The event name.

        Returns:
            callable: The handler for the event.
        """

        if event in self.handlers:
            return self.handlers[event]

        return lambda *args, **kwargs: None
