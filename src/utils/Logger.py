from logging import getLogger
from random import choice

from colorama import Fore as Color

available_colors = {
    Color.RED,
    Color.GREEN,
    Color.YELLOW,
    Color.BLUE,
    Color.MAGENTA,
    Color.CYAN,
    Color.WHITE,
    Color.LIGHTBLUE_EX,
    Color.LIGHTCYAN_EX,
    Color.LIGHTRED_EX,
}

server_used_colors = set()
client_used_colors = set()


def getServerLogger(name):
    color = choice(list(available_colors - server_used_colors))
    server_used_colors.add(color)
    return getLogger(f"{color}[{name}]{Color.RESET}")


def getClientLogger(name):
    color = choice(list(available_colors - client_used_colors))
    client_used_colors.add(color)
    return getLogger(f"{color}[{name}]{Color.RESET}")
