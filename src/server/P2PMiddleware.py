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
        uri, uuid = None, None
        user = self.users.get_user_by_name(data["username"])
        if user:
            uri, uuid = user.uri, user.uuid

        return False, {"uri": uri, "uuid": uuid}
