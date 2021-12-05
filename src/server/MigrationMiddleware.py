import os
import signal
from random import choice
from time import sleep, time

from socketio import Client

from src.utils.networking import change_server_addr

from ..utils.Logger import getServerLogger
from ..utils.Middleware import Middleware
from .Users import UserList

logger = getServerLogger("MigrationMiddleware")

SERVER_START_TIMEOUT = 10  # seconds


class MigrationMiddleware(Middleware):
    """Middleware encargado de manejar la logica de migracion"""

    def __init__(self, users: UserList, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.users = users

        self.__migrating = False

        self.handlers = {
            "connect": self.on_connect,
            "migrate": self.on_migrate,
        }

    def migrate(self):
        """Comenzar el proceso de migración"""

        selected_server = False
        new_address = None

        while not selected_server or new_address is None:
            clients = list(self.users.users.values())

            if len(clients) == 0:
                return False

            # Elegir un cliente al azar
            selected_client_sid = choice(clients).sid

            # Conectar y notificar migracion
            new_address = self.request_server_start(selected_client_sid)

            if new_address is None:
                continue

            selected_server = self.request_migration_connection(*new_address)

        # Pausar clientes
        self.send_pause_messaging_signal(True)

        # Mandar mensajes a nuevo server
        self.request_migration(new_address)
        return True

    def request_server_start(self, sid):
        """Mandar un mensaje al cliente para solicitar que empiece el proceso del server"""
        logger.debug("Requesting server start")

        done = False
        addr = None

        def cb(data):
            # Cliente retorna la ip y puerto del server que se acaba de crear
            nonlocal done, addr
            done = True
            addr = (data["ip"], data["port"])

        self.socketio.emit("server_start", {}, to=sid, callback=cb)

        end_time = time() + SERVER_START_TIMEOUT

        while not done:
            if end_time < time():
                logger.error("Server start timeout")
                return None

            sleep(0.1)

        return addr

    def request_migration_connection(self, ip, port):
        """
        Una vez que el nuevo server esta andando,
        se conecta con el para comezar la migracion
        """

        logger.debug("Requesting migration connection")
        addr = f"http://{ip}:{port}"

        try:
            self.client = Client()
            self.client.connect(addr, auth={"migration": True})
            return self.client.connected
        except Exception as e:
            logger.error(e)
            return False

    def send_pause_messaging_signal(self, pause=True):
        """Notificar a usuarios que encolen (o dejen de encolar) mensajes"""
        self.__migrating = pause
        self.socketio.emit("pause_messaging", pause)

    def request_migration(self, new_address):
        """
        Una vez conectado al nuevo server,
        se manda la informacion de la migracion
        """
        logger.debug("Requesting migration")

        data = {
            "messages": self.main_server.messages,
            "min_user_count": self.main_server.min_user_count,
            "history_sent": self.main_server.server_middleware.history_sent,
        }

        def on_ack(*_):
            # Una vez que el nuevo server recibe la informacion,
            # se desconecta de el, y se ejecuta el proceso de termino
            # de este server
            self.client.disconnect()
            self.client = None
            self.on_migrate_complete(new_address)

        self.client.emit("migrate", data, callback=on_ack)

    def on_migrate_complete(self, addr):
        """
        Una vez completada la migracion,
        se cambia la direccion del server
        y se notifica a los usuarios para que
        se reconecten
        """
        logger.debug("Migration complete")

        def cb(*_):
            # Al cambiar la direccion del server,
            # se notifica a los usuarios para que se reconecten,
            # se detiene este server y se termina el proceso
            self.socketio.emit("reconnect")
            self.main_server._created_server.shutdown()
            os.kill(os.getpid(), signal.SIGTERM)

        change_server_addr(
            self.main_server.dns_host,
            self.main_server.dns_port,
            self.main_server.server_uri,
            server_addr=f"http://{addr[0]}:{addr[1]}",
            self_addr=self.main_server.addr,
            callback=cb,
        )
        return True

    def __start(self):
        """Comenzar ciclo de migracion"""
        logger.debug("MigrationMiddleware started")

        while True:
            logger.debug("Waiting for cycle to end (30s)")
            sleep(30)

            logger.debug("Cycle ended, initiating migration")
            migration_success = self.migrate()

            if migration_success:
                logger.debug("Migration successful")
                break
            else:
                logger.debug("Migration failed, repeating cycle")

    def start(self):
        self.socketio.start_background_task(self.__start)

    def on_connect(self, sid, data):
        """
        Cuando se conecta alguien al server,
        si es para migrar se acepta la conexion y no se pasa el mensaje al siguiente middleware,
        si no, se pasa el mensaje al siguiente middleware (solo si no se esta migrando)
        """
        if "migration" in data and data["migration"]:
            logger.debug("Migration connection")
            return False, {}
        elif self.__migrating:
            logger.debug("Client connection while migrating")
            raise ConnectionRefusedError()
        else:
            return True, {}

    def on_migrate(self, sid, data):
        logger.debug("Migration request")
        self.main_server.messages = data["messages"]
        self.main_server.min_user_count = data["min_user_count"]
        self.main_server.history_sent = data["history_sent"]

        return False, {}
