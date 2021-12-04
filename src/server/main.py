from threading import Thread
from typing import List

from socketio import Server, WSGIApp
from werkzeug.serving import make_server

from src.server.ServerMiddleware import ServerMiddleware
from src.server.Users import UserList

from ..utils.Middleware import Middleware
from ..utils.Logger import getServerLogger
from ..utils.networking import (
    change_server_addr,
    get_public_ip,
    request_random_server,
    request_replica_addr,
    send_server_addr,
)

logger = getServerLogger("Main")


class MainServer:
    def __init__(self, dns_host: str, dns_port: int = 3000, min_user_count: int = 0, server_uri: str = "backend.com"):
        # Parameters
        self.dns_host = dns_host
        self.dns_port = dns_port
        self.min_user_count = min_user_count
        self.server_uri = server_uri

        # Middlewares
        self.middlewares: List[Middleware] = []
        self.first_middleware: Middleware = None

        # Socketio
        self.server = Server(cors_allowed_origins="*")
        self.app = WSGIApp(self.server)

        self.ip, self.port = get_public_ip()
        self.addr = f"http://{self.ip}:{self.port}"
        self.__created_server = make_server(
            self.ip,
            self.port,
            self.app,
            threaded=True,
        )

        # Connected Users
        self.users = UserList()

        # For debug
        self.simulate_server_down = False
        self.server_th = None

    def setup_middlewares(self):
        # ! Setup application middlewares

        # migration_middleware = MigrationMiddleware()
        # self.middlewares.append(migration_middleware)

        # replication_middleware = ReplicationMiddleware()
        # self.middlewares.append(replication_middleware)

        server_middleware = ServerMiddleware(self.users, self.server)
        self.middlewares.append(server_middleware)

        prev_middleware = None
        for middleware in self.middlewares:
            if prev_middleware is not None:
                prev_middleware.set_next(middleware)
            prev_middleware = middleware

        self.first_middleware = self.middlewares[0]

    def handle(self, event: str, sid: str, data: dict):
        if self.simulate_server_down:
            return False

        return self.first_middleware.handle(event, sid, data)

    def setup_events(self):
        self.server.on("connect", self.on_connect)
        self.server.on("disconnect", self.on_disconnect)
        self.server.on("*", self.handle)

    def register_in_dns(self):
        _, is_active_server = send_server_addr(self.dns_host, self.dns_port, self.server_uri, self.addr)
        if not is_active_server:
            logger.debug("No se pudo registrar en el DNS")
            exit(1)

    def __start(self):
        self.setup_middlewares()
        self.setup_events()
        self.register_in_dns()
        self.__created_server.serve_forever()

    def start(self):
        # ! Start server
        server_th = Thread(target=self.__start)
        server_th.start()

        while True:
            inp = input("Ingrese APAGAR o PRENDER para cambiar el estado del servidor: ")
            if inp == "APAGAR":
                logger.info("Apagando servidor")
                self.simulate_server_down = True
            elif inp == "PRENDER":
                logger.info("Prendiendo servidor")
                self.simulate_server_down = False
            elif inp == "TERMINAR":
                logger.info("Terminando servidor")
                self.__created_server.shutdown()
                break
            else:
                print("Comando no reconocido")

    def on_connect(self, sid: str, _, auth: dict):
        self.handle("connect", sid, auth)

    def on_disconnect(self, sid: str):
        self.handle("disconnect", sid, {})
