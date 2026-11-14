"""Prueba de humo del servicio publicado.

Uso: ``SMOKE_API_KEY=... python scripts/smoke.py <url>``. La clave se lee solo
del entorno (nunca de un argumento) y nunca se imprime.
"""

import sys
import time

import httpx

KEY_VARIABLE = "SMOKE_API_KEY"
# El plan free de Render puede tardar en despertar: tiempo generoso y un reintento
TIMEOUT_SECONDS = 60
HEALTH_ATTEMPTS = 2
RETRY_PAUSE_SECONDS = 5
QUESTION = {"question": "How many vacation days do I have?"}


def _report(passed, label):
    """Imprime ``[OK]`` o ``[FAIL]`` para una comprobacion y devuelve ``passed``."""
    print(f"{'[OK]' if passed else '[FAIL]'} {label}")
    return passed


def _status(call):
    """Ejecuta ``call`` y devuelve el codigo HTTP, o ``None`` si hubo un error."""
    try:
        return call().status_code
    except httpx.HTTPError:
        return None


def _health_status(url):
    """Consulta ``/health``, con un reintento si no responde 200."""
    status = None
    for attempt in range(HEALTH_ATTEMPTS):
        status = _status(lambda: httpx.get(f"{url}/health", timeout=TIMEOUT_SECONDS))
        if status == 200:
            break
        if attempt < HEALTH_ATTEMPTS - 1:
            time.sleep(RETRY_PAUSE_SECONDS)
    return status


def _ask_status(url, headers):
    """Hace ``POST /ask`` con los encabezados dados y devuelve el codigo HTTP."""
    return _status(
        lambda: httpx.post(
            f"{url}/ask", headers=headers, json=QUESTION, timeout=TIMEOUT_SECONDS
        )
    )


def main(argv, env):
    """Corre las tres comprobaciones; devuelve 0 si todas pasan.

    :param argv: argumentos sin el nombre del programa (la URL del servicio).
    :param env: mapa de variables de entorno (se lee ``SMOKE_API_KEY``).
    :return: 0 si todo pasa, 1 si algo falla o falta un dato.
    """
    if len(argv) != 1:
        print("Uso: SMOKE_API_KEY=... python scripts/smoke.py <url>")
        return 2
    key = env.get(KEY_VARIABLE)
    if not key:
        print(f"[FAIL] falta la variable de entorno {KEY_VARIABLE}")
        return 1
    url = argv[0].rstrip("/")
    results = [
        _report(_health_status(url) == 200, "/health responde 200"),
        _report(_ask_status(url, {}) == 401, "/ask sin clave responde 401"),
        _report(
            _ask_status(url, {"X-API-Key": key}) == 200, "/ask con clave responde 200"
        ),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    import os

    sys.exit(main(sys.argv[1:], os.environ))
