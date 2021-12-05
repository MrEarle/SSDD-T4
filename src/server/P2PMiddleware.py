from typing import Tuple

from .Users import UserList
from ..utils.Logger import getServerLogger
from ..utils.Middleware import Middleware

logger = getServerLogger("P2PMiddleware")


class P2PMiddleware(Middleware):
    def __init__(self, users: UserList, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.users = users

        self.handlers = {"addr_request": self.get_user_addr}

    def get_user_addr(self, sid: str, data: dict) -> Tuple[bool, dict]:
        """
        Si llega un evento de tipo addr_request,
        se obtiene la address del usuario de destino y se retorna
        """

        uri, uuid = None, None
        user = self.users.get_user_by_name(data["username"])
        if user:
            uri, uuid = user.uri, user.uuid

        # Este middleware no tiene que seguir avanzando, por lo que se retorna False
        # (La respuesta ya esta completa)
        return False, {"uri": uri, "uuid": uuid}
