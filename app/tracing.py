"""Trazas opcionales en LangSmith.

Sin ``LANGSMITH_TRACING=true`` y sin ``LANGSMITH_API_KEY`` no se importa
``langsmith`` ni se intenta ninguna conexion. La clave solo se lee del entorno.
"""

import functools

from app.observability import client_var, request_id_var

_STATE = {"client": None, "traceable": None}


def _hide(_data):
    """Reemplaza el contenido por un diccionario vacio."""
    return {}


def setup_tracing(config, env):
    """Enciende o apaga las trazas segun la configuracion.

    :param config: Configuracion de la aplicacion
    :type config: Config
    :param env: Variables de entorno (de ahi se lee la clave)
    :type env: Mapping[str, str]
    :return: ``True`` si las trazas quedaron encendidas
    :rtype: bool
    """
    _STATE["client"] = None
    _STATE["traceable"] = None
    if not config.langsmith_tracing or not env.get("LANGSMITH_API_KEY"):
        return False
    try:
        # pylint: disable-next=import-outside-toplevel
        import langsmith
    except ImportError:
        return False
    _STATE["client"] = langsmith.Client(
        api_key=env["LANGSMITH_API_KEY"],
        hide_inputs=_hide if config.hide_inputs else None,
        hide_outputs=_hide if config.hide_outputs else None,
    )
    _STATE["traceable"] = langsmith.traceable
    return True


def traced(name, run_type="chain"):
    """Decorador que envuelve la funcion con ``@traceable`` si hay trazas.

    El ``request_id`` y el nombre del cliente (nunca su clave) viajan en los
    metadatos de cada traza.

    :param name: Nombre de la traza
    :type name: str
    :param run_type: Tipo de corrida (``chain``, ``llm`` o ``tool``)
    :type run_type: str
    :return: El decorador
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            traceable = _STATE["traceable"]
            if traceable is None:
                return func(*args, **kwargs)
            # pylint: disable-next=not-callable
            decorate = traceable(
                name=name, run_type=run_type, client=_STATE["client"]
            )
            wrapped = decorate(func)
            extra = {
                "metadata": {
                    "request_id": request_id_var.get(),
                    "client": client_var.get(),
                }
            }
            return wrapped(*args, langsmith_extra=extra, **kwargs)

        return wrapper

    return decorator
