import logging
from time import sleep
from collections import deque
from src.client.start_server import start_server
from src.utils.networking import request_server_adrr

import socketio
from colorama import Fore as Color

from src.client.p2p import P2P

from .gui_socketio import GUI

logger = logging.getLogger(f"{Color.RED}[ClientSockets]{Color.RESET}")


class ClientSockets:
    def __init__(self, dns_ip: str, dns_port: int, server_uri: str) -> None:
        self.dns_host = dns_ip
        self.dns_port = dns_port
        self.server_uri = server_uri
        self.gui = GUI(self.server_connect, self.send_private_message, self.send_message)
        self.p2p = P2P()

        # Queue for outbound messages.
        # Should only send a message if the previous one was received by the server.
        self.__outbound = deque()
        self.__sendNext = False
        self.__pauseMessages = False

        self.flag = True
        self.reconnecting = False

    def initialize(self):
        # Initialize connection to server
        self.initialize_server_connection()

        # Initialize local server for p2p connections
        self.p2p.initialize_p2p_server(self.gui)

        # Get public url and port for p2p connection
        self.public_ip, self.port = self.p2p.start()

        # Deploy the chat GUI
        self.gui.initialize()

    def initialize_server_connection(self):
        # Initialize connection to server
        self.server_io = socketio.Client()

        # Register event handlers
        self.server_io.on("connect", self.connect)
        self.server_io.on("send_uuid", self.receive_uuid)
        self.server_io.on("server_message", self.server_message)
        self.server_io.on("chat", self.chat_message)
        self.server_io.on("message_history", self.chat_message_history)
        self.server_io.on("pause_messaging", self.receive_pause_messages_signal)
        self.server_io.on("reconnect", self.reconnect)
        self.server_io.on("server_start", self.on_create_server)

    def connect(self):
        logger.debug("Initializing chat GUI")
        self.gui.onConnect(self.reconnecting)

        # Start the message sending from queue in the background process
        logger.debug("Starting message delivery queue")
        if self.flag:
            self.server_io.start_background_task(self.__run)
            self.flag = False

    def reconnect(self):
        self.reconnecting = True
        self.server_io.disconnect()
        self.initialize_server_connection()
        self.server_connect(self.gui.name, self.reconnecting)
        return True

    def receive_uuid(self, uuid: str):
        pass

    def receive_pause_messages_signal(self, pause: bool):
        self.__pauseMessages = pause
        logger.debug(f"Received pause message with vaule {pause}")

    def server_message(self, data):
        # Cuando llega un mensaje del server, agregarlo en la gui
        self.gui.addMessage(data["message"])

    def chat_message(self, data):
        # Cuando llega un mensaje de un usuario, formatearlo
        # y agregarlo en la gui
        logger.debug(f"Chat received {data}")
        self.__on_deliver_message(data)

    def __on_deliver_message(self, message: dict):
        self.gui.addMessage(f"<{message['username']}> {message['message']}")

    def chat_message_history(self, data):
        # Si llega  la historia de mensaje, formatearlos y agregarlos
        # a la gui
        for msg in data["messages"]:
            self.gui.addMessage(f"<{msg[1]['username']}> {msg[1]['message']}")

    def __setSendNext(self, val: bool):
        # Utility function
        logger.debug("Send next")
        self.__sendNext = val

    def __run(self):
        # Constantly checks the queue for messages to send.
        # Only sends a message if the previous one has been
        # acknowledged by the server.
        self.__sendNext = True
        while True:
            if self.__outbound and self.__sendNext and not self.__pauseMessages:
                logger.debug(f"Outbound length: {len(self.__outbound)}")
                # Prevent other messages from being sent
                self.__sendNext = False

                # Get next message to send
                print("\n")
                print(self.__outbound)
                print("\n")
                msg = self.__outbound.popleft()

                # Send message to server, and allow next message to be sent
                # when the server responds to this message.
                logger.debug("Emmiting message to server")
                self.server_io.emit(
                    "chat",
                    msg,
                    callback=lambda *args: self.__setSendNext(True),
                )

            # Yield the CPU
            self.server_io.sleep(1e-4)  # 100 usec

    def server_connect(self, name, reconnecting=False):
        # Get server address
        server_address = request_server_adrr(self.dns_host, self.dns_port, self.server_uri)
        logger.debug(f"Obtained server address: {server_address}")
        # Connect to the server.
        # Sends session information, such as name, port and p2p server url.
        logger.debug(f"Connecting to server {self.server_uri}")
        self.server_io.connect(
            server_address,
            auth={"username": name, "publicUri": f"http://{self.public_ip}:{self.port}", "reconnecting": reconnecting},
        )
        self.__pauseMessages = False

    def send_message(self, message: str):
        # Appends a message to the outbound queue.
        # See __run for message sending.
        logger.debug(f"Sending message")
        self.__outbound.append({"message": message})

    def __send_private_message(self, addr, username, message, dest_user, dest_user_id):
        # Check if addr is valid. If it is None, destination user is not
        # connected to the server.
        if addr is None:
            self.gui.addMessage(f"User {dest_user} is not connected")
        else:
            self.p2p.send_private_message(addr, username, dest_user, dest_user_id, message)

    def send_private_message(self, dest_user, username, message):
        # Send a private message via p2p server
        def send_msg(arg_dict):  # addr, uuid):
            if arg_dict is None:
                self.gui.addMessage(f"User {dest_user} is not connected")
                return

            addr = arg_dict["uri"]
            uuid = arg_dict["uuid"]
            self.__send_private_message(addr, username, message, dest_user, uuid),

        try:
            # Ask server for destination p2p url.
            # Then, send the message to that url.
            self.server_io.emit(
                "addr_request",
                {"username": dest_user},
                callback=send_msg,
            )
        except TypeError:
            self.gui.addMessage("There was an error sending the private message, please try again.")

    def on_create_server(self, data):
        logger.debug(f"Creating server {data}")
        # Create a server
        ip, port = start_server()

        logger.debug(f"Server created at {ip}:{port}")
        return {"ip": ip, "port": port}
