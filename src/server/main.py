import os
import signal
from threading import Thread
from time import sleep
from typing import List

from socketio import Server, WSGIApp
from socketio.client import Client
from werkzeug.serving import make_server

from ..utils.Logger import getServerLogger
from ..utils.Middleware import Middleware
from ..utils.networking import get_public_ip, request_replica_addr, send_server_addr
from .MigrationMiddleware import MigrationMiddleware
from .P2PMiddleware import P2PMiddleware
from .ReplicationMiddleware import ReplicationMiddleware
from .DNSMiddleware import DNSMiddleware
from .ServerMiddleware import ServerMiddleware
from .Users import UserList

logger = getServerLogger("Main")


class MainServer:
    def __init__(
        self,
        dns_host: str,
        dns_port: int = 3000,
        min_user_count: int = 0,
        server_uri: str = "backend.com",
        server_ip: str = None,
        server_port: int = None,
        migrating: bool = False,
    ):
        # Parameters
        self.dns_host = dns_host
        self.dns_port = dns_port
        self.min_user_count = min_user_count
        self.server_uri = server_uri
        self.migrating = migrating

        # Middlewares
        self.middlewares: List[Middleware] = []
        self.first_middleware: Middleware = None

        # Socketio
        self.server: Server = Server(cors_allowed_origins="*")
        self.app = WSGIApp(self.server)

        if server_ip is None or server_port is None:
            ip, port = get_public_ip()

            if server_ip is None:
                self.ip = ip
            else:
                self.ip = server_ip

            if server_port is None:
                self.port = port
            else:
                self.port = server_port
        else:
            self.ip = server_ip
            self.port = server_port

        self.addr = f"http://{self.ip}:{self.port}"
        self._created_server = make_server(
            self.ip,
            self.port,
            self.app,
            threaded=True,
        )

        # Connected Users
        self.users = UserList()
        self.messages = {}

        self.events = set()

        # For debug
        self.simulate_server_down = False
        self.server_th = None

    def setup_middlewares(self):
        # ! Setup application middlewares

        self.dns_middleware = DNSMiddleware(self.users, self.server, main_server=self)
        self.middlewares.append(self.dns_middleware)

        self.migration_middleware = MigrationMiddleware(self.users, self.server, main_server=self)
        self.middlewares.append(self.migration_middleware)

        self.replication_middleware = ReplicationMiddleware(self.users, self.server, main_server=self)
        self.middlewares.append(self.replication_middleware)

        self.p2p_middleware = P2PMiddleware(self.users, self.server, main_server=self)
        self.middlewares.append(self.p2p_middleware)

        self.server_middleware = ServerMiddleware(
            self.users, self.messages, self.min_user_count, self.server, main_server=self
        )

        self.middlewares.append(self.server_middleware)

        prev_middleware = None
        for middleware in self.middlewares:
            for event in middleware.handlers:
                self.events.add(event)

            if prev_middleware is not None:
                prev_middleware.set_next(middleware)
            prev_middleware = middleware

        self.events.remove("connect")
        self.events.remove("disconnect")

        self.first_middleware = self.middlewares[0]

    def handle(self, event: str, sid: str, data: dict):
        logger.debug(f"Evento: {event} -> {data}")
        if self.simulate_server_down:
            logger.debug("Servidor apagado")
            return False

        result = self.first_middleware.handle(event, sid, data)
        logger.debug(f"Resultado: {result}")
        return result

    def get_handler(self, event_name: str):
        def handler(sid, data):
            return self.handle(event_name, sid, data)

        return handler

    def setup_events(self):
        self.server.on("connect", self.on_connect)
        self.server.on("disconnect", self.on_disconnect)

        for event in self.events:
            handler = self.get_handler(event)
            self.server.on(event, handler)

        print(self.server.handlers)

    def register_in_dns(self):
        if self.migrating:
            return

        print(self.addr)
        _, is_active_server = send_server_addr(self.dns_host, self.dns_port, self.server_uri, self.addr)
        if not is_active_server:
            logger.debug("No se pudo registrar en el DNS")
            os.kill(os.getpid(), signal.SIGTERM)
        # else:
        #     socket = Client()
        #     socket.connect(f"http://{self.dns_host}:{8001}")

    def __start(self):
        self.register_in_dns()
        self.setup_middlewares()
        self.setup_events()   
        self.migration_middleware.start()
        self._created_server.serve_forever()

    def start(self):
        # ! Start server
        server_th = Thread(target=self.__start, daemon=True)
        server_th.start()

        while True:
            inp = input("Ingrese APAGAR o PRENDER para cambiar el estado del servidor: ")
            if inp == "APAGAR":
                logger.info("Apagando servidor")
                self.simulate_server_down = True
                self.server.emit('server_down_dns')
                self.users = UserList()
                sleep(1)
                self.server.emit('server_down')
            elif inp == "PRENDER":
                logger.info("Prendiendo servidor")
                self.simulate_server_down = False
                self.register_in_dns()
            elif inp == "TERMINAR":
                logger.info("Terminando servidor")
                self._created_server.shutdown()
                break
            else:
                print("Comando no reconocido")

    def on_connect(self, sid: str, _, auth: dict):
        print("Se está conectando el dns")
        return self.handle("connect", sid, auth)

    def on_disconnect(self, sid: str):
        return self.handle("disconnect", sid, {})