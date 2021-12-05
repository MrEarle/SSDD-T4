from threading import Lock

from .Users import UserList
from ..utils.Middleware import Middleware


class ReplicationMiddleware(Middleware):
    """Este sería el middleware encargado de manejar la replicación de los servidores"""

    def __init__(self, users: UserList, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.users = users

        self.index_lock = Lock()
        self.next_index = 0

        self.handlers = {"chat": self.chat}

    def chat(self, sid: str, data: dict):
        """
        Si llega un evento 'chat', se procesa por aca y se le asigna el indice correspondiente.
        El mensaje se pasa al siguiente middleware para que eventualmente sea procesado por el
        servidor de chat.
        """

        client = self.users.get_user_by_sid(sid)

        if client is None:
            return False, {}

        with self.index_lock:
            data["message_index"] = self.next_index
            self.next_index += 1

        data["client_name"] = client.name

        return data
