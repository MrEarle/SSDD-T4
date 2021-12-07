from typing import Tuple

from ..utils.Logger import getServerLogger
from ..utils.Middleware import Middleware
from .Users import UserList

logger = getServerLogger("ServerMiddleware")


class ServerMiddleware(Middleware):
    """Midleware encargado de manejar la logica del chat"""

    def __init__(self, users: UserList, messages: dict, min_user_count: int, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.users = users
        self.min_user_count = min_user_count
        self.history_sent = False
        self.messages = messages

        self.handlers = {
            "connect": self.connect,
            "disconnect": self.disconnect,
            "chat": self.chat,
            "sync_next_index": self.chat,
            "sync_new_user": self.on_sync_new_user,
            "sync_new_user_reconnection": self.on_sync_reconnecting_user,
            "disconnect_synced_user": self.disconnect_synced_user,
            "update_p2p_uri": self.update_p2p_uri,
            "update_p2p_uri_replica": self.update_p2p_uri_forwarded
        }

    def update_p2p_uri_forwarded(self, sid: str, data: dict):
        logger.info("Updating uri data in replica")
        if "username" in data:
            user = self.users.get_user_by_name(data["username"])
            if user:
                self.users.del_user(user.sid)
                self.users.add_user(user.name, sid, data["publicUri"], user.replicated, uri_update=True)
            else:
                logger.error(f"Couldn't find user {data['username']} to update its uri")

    def update_p2p_uri(self, sid: str, data: dict):
        logger.info("Updating uri data")
        if "username" in data:
            user = self.users.get_user_by_name(data["username"])
            if user:
                self.users.del_user(user.sid)
                self.users.add_user(user.name, sid, data["publicUri"], user.replicated, uri_update=True)
            else:
                logger.error(f"Couldn't find user {data['username']} to update its uri")
        return True

    def connect(self, sid, data):
        logger.debug(f"User logging in with auth: {data}")
        user = self.users.add_user(data["username"], sid, data["publicUri"], replicated="replicated" in data)

        if user is None:
            logger.debug(f'Username {data["username"]} is already taken')
            raise ConnectionRefusedError("Username is invalid or already taken")

        if not data["reconnecting"]:
            self.socketio.emit(
                "server_message",
                {"message": f'\u2713 {data["username"]} has connected to the server'},
            )
        if not user.replicated:
            self.socketio.emit("send_uuid", user.uuid, to=sid)

            # Si se supero el limite inferior de usuarios conectados, mandar la historia
            if len(self.users) >= self.min_user_count and not data["reconnecting"]:
                logger.debug(f"Sending history")

                if self.history_sent:
                    # Solo al cliente conectado si ya se mando a todos
                    self.socketio.emit(
                        "message_history",
                        {"messages": [x for x in sorted(self.messages.items())]},
                        to=sid,
                    )
                else:
                    # A todos si todavia no se hace
                    self.socketio.emit("message_history", {"messages": [x for x in sorted(self.messages.items())]})
                    self.history_sent = True

            logger.debug(f"{user.name} connected with sid {user.sid}")

    def on_sync_new_user(self, sid: str, data: dict):
        data["replicated"] = True
        self.connect(sid, data)

    def on_sync_reconnecting_user(self, sid: str, data: dict):
        pass

    def disconnect_synced_user(self, sid1: str, sid: str):
        # Obtener el usuario, si existe
        client = self.users.get_user_by_sid(sid)
        if client:
            self.users.del_user(sid)

    def disconnect(self, sid, _):
        # Obtener el usuario, si existe
        client = self.users.get_user_by_sid(sid)
        if client and not client.replicated:
            logger.debug(f"User disconnected: {client.name}")

            # Notificar al resto que el usuario se desconecto
            self.socketio.emit(
                "server_message",
                {"message": f"\u274C {client.name} has disconnected from the server"},
            )

    def chat(self, sid: str, data: dict):
        """Maneja el broadcast de los chats"""
        # Obtener el cliente que mando el mensaje
        client_name = data["client_name"]

        # Agregar mensaje al registro
        if "message_index" in data:
            self.messages[data["message_index"]] = {"username": client_name, "message": data["message"]}

        # Mandar mensaje a todos los clientes, solo si se supera el n
        if len(self.users) >= self.min_user_count or self.history_sent:
            logger.debug(f"Sending message to all clients")
            for user in self.users.users.values():
                try:
                    msg = data.copy()
                    msg["username"] = client_name
                    msg["index"] = data["message_index"]
                    self.socketio.emit("chat", msg, to=user.sid)
                except Exception as e:
                    logger.error(f"Error: {e}")

        return {"status": "ok"}
