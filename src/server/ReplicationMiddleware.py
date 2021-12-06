from threading import Lock

from socketio.client import Client

from src.utils.networking import request_replica_addr

from .Users import UserList
from ..utils.Logger import getServerLogger
from ..utils.Middleware import Middleware

logger = getServerLogger("ReplicationMiddleware")


class ReplicationMiddleware(Middleware):
    """Este sería el middleware encargado de manejar la replicación de los servidores"""

    def __init__(self, users: UserList, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.replica_client = None
        self.users = users

        self.index_lock = Lock()
        self.next_index = 0

        self.handlers = {"chat": self.chat, "connect": self.connect,
                         "connect_other_server": self.connect_other}

        self.connect_replica()

    def connect_replica(self):
        replica_address = request_replica_addr(self.main_server.dns_host, self.main_server.dns_port,
                                               self.main_server.addr,
                                               self.main_server.server_uri)  # Se obtiene el address de la replica
        if replica_address:
            print('\nConnecting to replica server')
            self.replica_client = Client()
            # Aqui tenemos un cliente para comunicarnos con la replica
            try:
                self.replica_client.connect(replica_address, auth={
                    "replica_addr": self.main_server.addr})
                self.replica_client.emit('connect_other_server', data={
                    'replica_addr': self.main_server.addr})
            except Exception:
                pass

    def connect_other(self, sid: str, data: dict):
        if self.replica_client:
            self.replica_client.disconnect()
        else:
            self.replica_client = Client()

        self.replica_client.connect(data['replica_addr'], auth={
            "replica_addr": self.main_server.addr})

    def connect(self, sid: str, data: dict):
        if "replica_addr" in data:
            return False, {}
        else:
            return None

    def chat(self, sid: str, data: dict):
        """
        Si llega un evento 'chat', se procesa por aca y se le asigna el indice correspondiente.
        El mensaje se pasa al siguiente middleware para que eventualmente sea procesado por el
        servidor de chat.
        """
        if not "client_name" in data:
            client = self.users.get_user_by_sid(sid)

            if client is None:
                return False, {}
            
            data["client_name"] = client.name

        with self.index_lock:
            data["message_index"] = self.next_index
            self.next_index += 1

        if 'forwarded' in data and data['forwarded']:
            logger.debug(f"New message from replica")
            return True, data
        
        if not 'forwarded' in data:
            data['forwarded'] = True
            logger.debug(f"Sending new message to replica")
            self.replica_client.emit('chat', data)

        return data
