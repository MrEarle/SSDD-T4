from abc import abstractmethod
from typing import Tuple
from socketio import Server


class Middleware():
    def __init__(self, socketio: Server, next_middleware=None):
        self.socketio = socketio
        self.next_middleware = next_middleware

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
                ret_val = ret_val.update(next_ret_val)

        return ret_val

    @abstractmethod
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
        pass_next = True
        ret_val = {}
        # ! Handle event here.
        # ! Return pass_next = False if you don't want to pass the event to the next middleware.
        # ! Return ret_val if you want to return a value to the client.

        return pass_next, ret_val
