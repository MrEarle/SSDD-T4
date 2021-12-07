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

        self.handlers = {
            "chat": self.chat,
            "connect": self.connect,
            "connect_other_server": self.connect_other,
            "sync_next_index": self.on_sync_next_index
        }

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
            # User connected
            if "username" in data:
                if self.replica_client and self.replica_client.connected:
                    self.replica_client.emit('sync_new_user', data)
            return None

    def on_sync_next_index(self, sid: str, data: dict):
        # Calcular el indice a asignar
        with self.index_lock:
            # Indice a asignar segun otro server
            remote_next_index = data["message_index"]

            # Indice a asignar segun este server
            local_next_index = self.next_index

            # Indice a asignar segun ambos
            next_index = max(remote_next_index, local_next_index)

            # Actualizar localmente el siguiente indice
            self.next_index = max(self.next_index, next_index) + 1

        return {"next_index": next_index}

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

        def callback(response: dict):
            with self.index_lock:
                self.next_index = max(self.next_index, response["next_index"]) + 1

        if self.replica_client and self.replica_client.connected:
            try:
                with self.index_lock:
                    logger.debug(f"Sending new message to replica")
                    data["message_index"] = self.next_index
                    self.replica_client.emit('sync_next_index', data, callback=callback)
            except Exception:
                pass
        else:
            data["message_index"] = self.next_index
            self.next_index = self.next_index + 1         
        return data
