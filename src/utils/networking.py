import socket
import pickle
from time import sleep
from typing import Tuple
import logging
from colorama import Fore as Color

logger = logging.getLogger(f"{Color.LIGHTBLUE_EX}[Networking]{Color.RESET}")


def get_public_ip() -> Tuple[str, int]:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        public_ip = s.getsockname()[0]
        port = s.getsockname()[1]
    return public_ip, port


def request_server_adrr(dns_host: str, dns_port: int, uri: str) -> str:
    msg = pickle.dumps({"name": "addr_request", "uri": uri})

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((dns_host, dns_port))
        s.send(msg)

        while True:
            response = s.recv(2048)
            response: dict = pickle.loads(response)

            if response["name"] == "addr_response" and response.get("req_uri", "") == uri:
                return response["addr"]


def request_replica_addr(dns_host: str, dns_port: int, my_addr: str, uri: str) -> str:
    msg = pickle.dumps({
        "name": "get_replica_addr",
        "my_addr": my_addr,
        "uri": uri
    })

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((dns_host, dns_port))
        s.send(msg)

        while True:
            response = s.recv(2048)
            response: dict = pickle.loads(response)

            if response["name"] == "get_replica_addr_response":
                return response["addr"]


def send_server_addr(dns_host: str, dns_port: int, server_uri: str, server_addr: str) -> str:
    msg = pickle.dumps({"name": "update_server", "addr": server_addr, "uri": server_uri})

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((dns_host, dns_port))

    s.sendall(msg)

    while True:
        try:
            response = s.recv(2048)
            response: dict = pickle.loads(response)

            if response["name"] == "update_server_response":
                s.close()
                return response["addr"], response["active_server"]
        except ConnectionResetError:
            pass
        sleep(0.1)

def change_server_addr(
    dns_host: str, dns_port: int, server_uri: str, server_addr: str, self_addr: str, callback
) -> str:
    msg = pickle.dumps({"name": "set_current_server", "addr": server_addr, "uri": server_uri, "self_addr": self_addr})

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((dns_host, dns_port))

    s.sendall(msg)

    while True:
        try:
            response = s.recv(2048)
            response: dict = pickle.loads(response)

            if response["name"] == "set_current_server_response":
                s.close()
                break
        except ConnectionResetError:
            pass
        sleep(0.1)

    callback()


def request_random_server(dns_host: str, dns_port: int, self_uri: str) -> str:
    msg = pickle.dumps({"name": "get_random_server", "uri": self_uri})
    logger.debug(f"Connecting to DNS at {dns_host}:{dns_port}")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((dns_host, dns_port))

    s.sendall(msg)

    while True:
        try:
            response = s.recv(2048)
            response: dict = pickle.loads(response)

            if response["name"] == "random_server_response":
                s.close()
                return response["addr"]
        except ConnectionResetError:
            pass
        sleep(0.1)
