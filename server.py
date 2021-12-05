import logging
import socket
from argparse import ArgumentParser
from src.server.main import MainServer


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
parser.add_argument(
    "-n",
    "--min_n",
    default=0,
    help="Minimum number of clients before starting the connection.",
    type=int,
)

parser.add_argument("--server_ip", help="Optional. Server ip", type=str, default=None)
parser.add_argument("--server_port", help="Optional. Server port", type=int, default=None)
parser.add_argument("--migrating", help="Dont use", default=False, action="store_true")

if __name__ == "__main__":
    args = parser.parse_args()

    # Server en otro thread
    server = MainServer(
        args.dns_ip,
        args.dns_port,
        args.min_n,
        args.server_uri,
        server_ip=args.server_ip,
        server_port=args.server_port,
        migrating=args.migrating,
    )
    server.start()
