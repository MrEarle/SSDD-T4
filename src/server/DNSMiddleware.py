from typing import Tuple

from ..utils.Logger import getServerLogger
from ..utils.Middleware import Middleware

logger = getServerLogger("DNSMiddleware")

class DNSMiddleware(Middleware):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.handlers = {"connect": self.connect}

    def connect(self, sid: str, data: dict) -> Tuple[bool, dict]:
        """
        Si llega un evento de tipo connect con auth: dns_polling,
        se acepta la conexión y se termina 
        """
        if ('dns_polling' in data):
            logger.debug('Ha llegado la conexión del DNS')

            # Este middleware no tiene que seguir avanzando, por lo que se retorna False
            # (La respuesta ya esta completa)
            return False, {"status": "OK"}
        return True, {}
