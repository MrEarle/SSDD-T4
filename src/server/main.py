from logging import log
from threading import Thread
from typing import List

from socketio import Server, WSGIApp
from werkzeug.serving import make_server

from src.server.ReplicationMiddleware import ReplicationMiddleware

from ..utils.Logger import getServerLogger
from ..utils.Middleware import Middleware
from ..utils.networking import get_public_ip, send_server_addr
from .P2PMiddleware import P2PMiddleware
from .ServerMiddleware import ServerMiddleware
from .Users import UserList

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
        self.server: Server = Server(cors_allowed_origins="*", logger=logger)
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
        self.events = set()

        # For debug
        self.simulate_server_down = False
        self.server_th = None

    def setup_middlewares(self):
        # ! Setup application middlewares

        # migration_middleware = MigrationMiddleware()
        # self.middlewares.append(migration_middleware)

        replication_middleware = ReplicationMiddleware(self.users, self.server)
        self.middlewares.append(replication_middleware)

        p2p_middleware = P2PMiddleware(self.users, self.server)
        self.middlewares.append(p2p_middleware)

        server_middleware = ServerMiddleware(self.users, self.min_user_count, self.server)
        self.middlewares.append(server_middleware)

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
        return self.handle("connect", sid, auth)

    def on_disconnect(self, sid: str):
        return self.handle("disconnect", sid, {})
