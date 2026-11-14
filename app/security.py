"""Claves por cliente y limite de peticiones.

Ninguna funcion de este modulo escribe una clave en un mensaje de error: solo
se nombran la posicion de la entrada y su largo.
"""

import hmac
import math
import threading
from collections import deque


def parse_api_keys(raw):
    """Convierte ``cliente:clave,cliente2:clave2`` en un mapa cliente a clave.

    :param raw: Valor de ``API_KEYS`` (puede estar vacio)
    :type raw: str
    :return: Mapa de nombre de cliente a clave
    :rtype: dict
    :raises ValueError: Si una entrada esta mal formada o repetida; el error
        dice la posicion y el largo de la entrada, nunca su valor
    """
    keys = {}
    if not raw.strip():
        return keys
    for index, entry in enumerate(raw.split(","), start=1):
        name, separator, key = entry.strip().partition(":")
        name = name.strip()
        key = key.strip()
        where = f"API_KEYS entry {index} (length {len(entry.strip())})"
        if not separator or not name or not key:
            raise ValueError(f"{where} must have the form client:key")
        if name in keys:
            raise ValueError(f"{where} repeats a client name")
        if any(hmac.compare_digest(key, known) for known in keys.values()):
            raise ValueError(f"{where} repeats a key")
        keys[name] = key
    return keys


def authenticate(api_keys, provided):
    """Busca el cliente dueno de la clave recibida.

    Con un mapa vacio nunca autentica: no existe un modo abierto.

    :param api_keys: Mapa de cliente a clave
    :type api_keys: dict
    :param provided: Valor del encabezado ``X-API-Key`` o ``None``
    :type provided: str or None
    :return: El nombre del cliente, o ``None`` si la clave no es valida
    :rtype: str or None
    """
    if not provided:
        return None
    candidate = provided.encode("utf-8")
    found = None
    # Se recorren todas las claves para no revelar cual coincidio por tiempo.
    for name, key in api_keys.items():
        if hmac.compare_digest(candidate, key.encode("utf-8")):
            found = name
    return found


class RateLimiter:
    """Ventana deslizante de peticiones por cliente, con reloj inyectado.

    :param limit: Peticiones permitidas por ventana
    :type limit: int
    :param clock: Funcion sin argumentos que devuelve segundos (``float``)
    :type clock: Callable
    :param window_seconds: Largo de la ventana en segundos
    :type window_seconds: int
    """

    def __init__(self, limit, clock, window_seconds=60):
        self._limit = limit
        self._clock = clock
        self._window = window_seconds
        self._lock = threading.Lock()
        self._marks = {}

    def check(self, client):
        """Cuenta una peticion del cliente si cabe en la ventana.

        :param client: Nombre del cliente
        :type client: str
        :return: 0 si la peticion pasa; si no, los segundos de espera (>= 1)
        :rtype: int
        """
        with self._lock:
            now = self._clock()
            marks = self._marks.setdefault(client, deque())
            while marks and now - marks[0] >= self._window:
                marks.popleft()
            if len(marks) >= self._limit:
                return max(1, math.ceil(marks[0] + self._window - now))
            marks.append(now)
            return 0
