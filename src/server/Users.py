import logging
from collections import namedtuple
from typing import Dict, Optional, Union
from uuid import uuid4

logger = logging.getLogger("[UserList]")


User = namedtuple("User", ["name", "uuid", "uri", "sid", "replicated", "disconnected"])


class UserList:
    def __init__(self) -> None:
        self.users: Dict[str, User] = {}

    """
    Adds a new user to global dictionary
        username: Handle for this user
        roomnane: Room of the user
        sid: Session ID for the user
    """

    def add_user(self, username: str, sid: str, uri: str, replicated: bool, uri_update=False) -> Optional[User]:
        old_user = self.get_user_by_name(username)
        if not username or old_user:
            if uri_update:
                self.del_user(old_user.sid)
            elif old_user.disconnected:
                self.del_user(old_user.sid)
                user = User(old_user.name, old_user.uuid, uri, sid, old_user.replicated, False)
                self.users[sid] = user
                return user
            else:
                logger.debug(f"Username with name {username} already exists. Users:", self.users)
                if old_user.replicated:
                    logger.debug("Old user is replicated, we're just gonna assume the real one is arriving.")
                    self.del_user(old_user.sid)
                else:
                    if replicated:
                        return old_user
                    return None
        uuid = str(uuid4())
        user = User(username, uuid, uri, sid, replicated, False)
        self.users[sid] = user
        return user

    """
    Gets a user based on the session ID
        sid: SID for the user
    """

    def get_user_by_sid(self, sid: str) -> Union[User, None]:
        if sid in self.users:
            return self.users[sid]
        return None

    """
    gets a user based on user handle
        name: Handle for this user
    """

    def get_user_by_name(self, name: str) -> Union[User, None]:
        for _, value in self.users.items():
            if value.name.upper() == name.upper():
                return value
        return None

    def get_user_by_uuid(self, uuid: str) -> Union[User, None]:
        for _, value in self.users.items():
            if value.uuid == uuid:
                return value
        return None

    """
    Deletes a user from global dictionary
        roomnane: Room of the user
        sid: SID for the user
    """

    def del_user(self, sid: str) -> Union[User, None]:
        user = None
        if sid in self.users:
            user = self.users[sid]
            self.users[sid] = User(user.name, user.uuid, user.uri, user.sid, user.replicated, True)

        return user

    def __len__(self):
        return len(self.users)
