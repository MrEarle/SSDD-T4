"""Implementation of a simple Name Server with SSP (stub, scion pairs)
Chains, this is a simple solution for locating entities that is mainly
applicable to local-area networks.

 - Server should have a migration protocol: marshalls the


"""
import logging
import pickle as pkl
from datetime import datetime
from re import U
import socket
from threading import Thread
from random import choice, sample

from colorama.ansi import Fore
from socketio import Server
from socketio.client import Client
from socketio.middleware import WSGIApp
from werkzeug.serving import make_server

from .ip_lookup import find_closest_ip
from .rw_lock import get_rwlock

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(f"{Fore.GREEN}[DNS]{Fore.RESET}")


def ctime():
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    return current_time


class NameServer:
    def __init__(self, port=8000, n=10, socketio_port=8001):
        """Initializes a name server with forwarding pointers of the form
        (stub, scion) for clients stubs and server stubs.

        The objective of this class is to provide an approach for locating
        mobile entities via following a chain of forwarding pointers.

        Forwarding Pointer example: (stub, scion), where stub is the client
        stub and scion is the server stub. When the scion is null, the stub
        points to the actual object, else

        Parameters
        ----------
        port : int
            Port on which the server will be listening for requests
        n : int
            Maximum number of processes to listen
        """
        self.host = socket.gethostbyname(socket.gethostname())
        self.port = port
        self.n = n

        self.server_reader, self.server_writer = get_rwlock()

        self.addresses = set()  # set(http://ip:port)
        self.uri2address = dict()  # uri -> [address1, address2, ...]

        # initialize NS
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind((self.host, self.port))
        self.s.listen(n)

        logger.debug(f"[{ctime()}] Name Server up and running on" f" IP: {self.host}, PORT: {self.port}")

    def run(self):
        """Runs the Name Server"""

        logger.debug(f"[{ctime()}] Accepting connections")
        while True:
            logger.debug(f"[{ctime()}] Waiting for next connection")
            (conn, addr) = self.s.accept()
            if conn:
                client_th = Thread(target=self.accept_connection, args=[conn, addr])
                client_th.start()

    def on_disconnect(self, address: str, uri: str):
        logger.debug(f"[{ctime()}] Server with address {address} is disconnected")

        # Eliminamos la address del registro DNS
        if address in self.uri2address[uri] and address in self.addresses:
            self.uri2address[uri].remove(address)
            self.addresses.remove(address)

    def accept_connection(self, conn: socket.socket, addr):
        """Manages a connection

        Incoming requests must come with the following structure:

        {
            name: The type of request
            ...other_data: Data relevant to the request type
        }
        """

        logger.debug(f"[{ctime()}] Accepted connection from " f"IP: {addr[0]}, PORT: {addr[1]}")

        while True:
            try:
                data = conn.recv(1024)
                req = pkl.loads(data)

                if req["name"] == "update_server":  # nuevo proceso latente
                    active_server = self.register_address(req["uri"], req["addr"])
                    msj = {"name": "update_server_response", "addr": req["addr"], "active_server": active_server}
                    conn.send(pkl.dumps(msj))
                    logger.debug(f"[{ctime()}] Added new server location:" f" {req['addr']}")
                    
                    def on_disconnect():
                        self.on_disconnect(req['addr'], req['uri'])


                    client = Client(reconnection=False)
                    client.connect(req['addr'], auth={'dns_polling': True})
                    client.on('disconnect', on_disconnect)

                    def on_server_down():
                        client.disconnect()
                    client.on('server_down_dns', on_server_down)

                elif req["name"] == "addr_request":
                    closest_ip = self.get_closest_server(addr[0], req["uri"])
                    msj = {
                        "name": "addr_response",
                        "req_uri": req["uri"],
                        "addr": closest_ip,
                        "status": (200 if closest_ip else 404),
                    }
                    conn.send(pkl.dumps(msj))
                    logger.debug(f"[{ctime()}] Last known location sent to client: {req['uri']} -> {msj['addr']}")

                elif req["name"] == "get_random_server":
                    msj = {
                        "name": "random_server_response",
                        "addr": self.get_random_server(req["uri"]),
                    }
                    conn.send(pkl.dumps(msj))

                elif req["name"] == "set_current_server":
                    self.set_current_host(req["uri"], req["addr"], req["self_addr"])
                    msj = {"name": "set_current_server_response"}
                    conn.send(pkl.dumps(msj))

                elif req["name"] == "get_replica_addr":
                    logger.debug(f"[{ctime()}] Send replica address")
                    msj = {
                        "name": "get_replica_addr_response",
                        "addr": self.get_replica_address(req["my_addr"], req["uri"]),
                    }
                    conn.send(pkl.dumps(msj))

                else:
                    logger.debug(f"[{ctime()}] Message didnt match")
                    msj = {"name": "empty"}
                    conn.send(pkl.dumps(msj))

                break
            except pkl.UnpicklingError as e:
                logger.debug(e)
        logger.debug(f"[{ctime()}] Closing connection from " f"IP: {addr[0]}, PORT: {addr[1]}")

        conn.close()

    def get_closest_server(self, ip: str, uri: str) -> str:
        with self.server_reader:
            servers = self.uri2address.get(uri)
            if servers:
                return find_closest_ip(ip, sample(servers, len(servers)))
            return None

    def register_address(self, uri: str, address: str) -> bool:
        """Receives a new host:port from the server host and update the list
        of known URIs.

        Parameters
        ----------
        uri : str
        adress : str

        Returns
        ----------
        Bool -> True if set as active server
        """
        self.addresses.add(address)

        is_active_server = False

        with self.server_writer:
            if not self.uri2address.get(uri):
                self.uri2address[uri] = []

            if len(self.uri2address[uri]) < 2:
                self.uri2address[uri].append(address)
                is_active_server = True

        return is_active_server

    def get_replica_address(self, request_address: str, uri: str) -> str:
        for address in self.uri2address[uri]:
            if address != request_address:
                return address
        return ""

    def set_current_host(self, uri: str, address: str, old_address: str):
        with self.server_writer:
            try:
                i = self.uri2address[uri].index(old_address)
                self.uri2address[uri][i] = address
                logger.debug(f"Set current host addr: {address}")
            except ValueError as e:
                logger.error(
                    f"Trying to update address from {old_address} to {address}, but there's no {old_address} in the registry."
                )

    def get_random_server(self, uri: str):
        with self.server_reader:
            servers = [addr for addr in self.addresses if (addr and addr not in self.uri2address[uri])]

            if len(servers) == 0:
                return None

            return choice(servers)


def serve():
    PORT = 8000
    SOCKETIO_PORT = 8001
    n = 10
    ns = NameServer(PORT, n, SOCKETIO_PORT)

    ns.run()


if __name__ == "__main__":
    serve()
