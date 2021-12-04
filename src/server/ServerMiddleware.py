from typing import Tuple

from src import client

from ..utils.Middleware import Middleware
from ..utils.Logger import getServerLogger
from .Users import UserList

logger = getServerLogger("ServerMiddleware")


class ServerMiddleware(Middleware):
    def __init__(self, users: UserList, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.users = users
        self.history_sent = False
        self.messages = {}

        self.handlers = {
            "connect": self.connect,
            "disconnect": self.disconnect,
        }

    def __handle(self, event: str, sid: str, data: dict) -> Tuple[bool, dict]:
        handler = self.handlers.get(event, lambda *args, **kwargs: None)
        handler_result = handler(sid, data)

        if isinstance(handler_result, tuple):
            return handler_result
        elif isinstance(handler_result, dict):
            return True, handler_result
        else:
            return True, {}

    def connect(self, sid, data):
        logger.debug(f"User logging in with auth: {data}")
        user = self.users.add_user(data["username"], sid, data["publicUri"])

        if user is None:
            logger.debug(f'Username {data["username"]} is already taken')
            raise ConnectionRefusedError("Username is invalid or already taken")

        if not data["reconnecting"]:
            self.socketio.emit(
                "server_message",
                {"message": f'\u2713 {data["username"]} has connected to the server'},
            )

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

    def disconnect(self, sid, _):
        # Obtener el usuario, si existe
        client = self.users.get_user_by_sid(sid)
        if client:
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
        self.messages[data["message_index"]] = {"username": client_name, "message": data["message"]}

        # Mandar mensaje a todos los clientes, solo si se supera el n
        if len(self.users) >= self.min_user_count or self.history_sent:
            for user in self.users.users.values():
                try:
                    msg = data.copy()
                    msg["username"] = client_name
                    msg["index"] = data["message_index"]
                    self.socketio.emit("chat", msg, to=user.sid)
                except Exception as e:
                    logger.error(f"Error: {e}")
