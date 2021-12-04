import logging
from collections import namedtuple
from typing import Dict, Optional, Union
from uuid import uuid4

logger = logging.getLogger("[UserList]")


User = namedtuple("User", ["name", "uuid", "uri", "sid"])


class UserList:
    def __init__(self) -> None:
        self.users: Dict[str, User] = {}

    """
    Adds a new user to global dictionary
        username: Handle for this user
        roomnane: Room of the user
        sid: Session ID for the user
    """

    def add_user(self, username: str, sid: str, uri: str) -> Optional[User]:
        if not username or self.get_user_by_name(username):
            logger.debug(f"Username with name {username} already exists. Users:", self.users)
            return None
        uuid = str(uuid4())
        user = User(username, uuid, uri, sid)
        self.users[uuid] = user
        return user

    """
    Gets a user based on the session ID
        sid: SID for the user
    """

    def get_user_by_uuid(self, uuid: str) -> Union[User, None]:
        if uuid in self.users:
            return self.users[uuid]
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

    def get_user_by_sid(self, sid: str) -> Union[User, None]:
        for _, value in self.users.items():
            if value.sid == sid:
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
            del self.users[sid]

        return user

    def __len__(self):
        return len(self.users)
