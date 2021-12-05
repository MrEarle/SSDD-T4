from subprocess import Popen
from inspect import getsourcefile
from os import path
import sys
from typing import Tuple

from ..utils.networking import get_public_ip


def start_server() -> Tuple[str, int]:
    ip, port = get_public_ip()

    # ./src/client
    exec_path, _ = path.split(path.abspath(getsourcefile(lambda: 0)))

    # ./src
    exec_path, _ = path.split(exec_path)

    # .
    exec_path, _ = path.split(exec_path)

    exec_path = path.join(exec_path, "server.py")
    print(exec_path)

    command = [sys.executable, exec_path, "--server_ip", ip, "--server_port", str(port), "--migrating"]
    if sys.platform == "linux":
        command = ["xterm", "-e"] + command
        Popen(command)
    else:
        from subprocess import CREATE_NEW_CONSOLE

        Popen(command, creationflags=CREATE_NEW_CONSOLE)

    return ip, port
