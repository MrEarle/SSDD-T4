from argparse import ArgumentParser
import socket
from src.client.client_socket import ClientSockets
import logging

logging.basicConfig(level=logging.DEBUG)

parser = ArgumentParser()

parser.add_argument(
    "--dns_ip",
    default=socket.gethostbyname(socket.gethostname()),
    help="Domain name server ip",
    type=str,
)
parser.add_argument(
    "--dns_port",
    default=8000,
    help="Domain name server port",
    type=int,
)
parser.add_argument(
    "-u",
    "--server_uri",
    default="backend.com",
    help="Server URI",
    type=str,
)

if __name__ == "__main__":
    args = parser.parse_args()

    client = ClientSockets(args.dns_ip, args.dns_port, args.server_uri)
    client.initialize()
