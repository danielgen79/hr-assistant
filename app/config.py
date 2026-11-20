"""Lectura y validacion de la configuracion desde variables de entorno."""

from dataclasses import dataclass, field
from typing import Dict, Mapping

from app.security import parse_api_keys

DEFAULT_ENVIRONMENT = "development"
ENVIRONMENTS = ("development", "production")
DEFAULT_RATE_LIMIT_PER_MINUTE = 30
DEFAULT_MODEL_PROVIDER = "fake"
DEFAULT_AGENT_MAX_STEPS = 3
DEFAULT_MAX_QUESTION_CHARS = 2000
DEFAULT_EMPLOYEES_PATH = "data/employees.json"
DEFAULT_SERVICE_NAME = "hr-assistant"
DEFAULT_SLO_P95_MS = 2000
DEFAULT_CF_GATEWAY_ID = "default"
DEFAULT_MODEL_SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
DEFAULT_MODEL_LARGE = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
DEFAULT_ROUTER_MAX_CHARS = 80
DEFAULT_HISTORY_WINDOW = 6
DEFAULT_MODEL_MAX_TOKENS = 300
DEFAULT_PRICES_PATH = "data/model_prices.json"
PII_MODES = ("mask", "block")
DEFAULT_PII_MODE = "mask"
DEFAULT_MAX_HISTORY_MESSAGES = 20
DEFAULT_MAX_ANSWER_CHARS = 4000


@dataclass(frozen=True)
class Config:  # pylint: disable=too-many-instance-attributes
    """Configuracion inmutable de la aplicacion.

    :param model_provider: Nombre del proveedor del modelo
    :param agent_max_steps: Tope de vueltas del bucle del agente
    :param max_question_chars: Largo maximo de la pregunta
    :param employees_path: Ruta del archivo de empleados
    :param service_name: Valor del campo ``service`` del log
    :param slo_p95_ms: Meta de latencia p95 en milisegundos
    :param langsmith_tracing: Si se enciende el envio de trazas
    :param hide_inputs: Si se ocultan las entradas en las trazas
    :param hide_outputs: Si se ocultan las salidas en las trazas
    :param cf_account_id: Cuenta de Cloudflare
    :param cf_gateway_id: Gateway de Cloudflare
    :param cf_api_token: Token de Cloudflare (secreto, no sale en ``repr``)
    :param model_small: Modelo barato
    :param model_large: Modelo capaz
    :param routing: Si se enruta cada pregunta
    :param router_max_chars: Largo desde el que la pregunta va al modelo capaz
    :param history_window: Mensajes de historial que se mandan al modelo
    :param model_max_tokens: Tope de tokens de salida
    :param model_temperature: Temperatura del modelo
    :param cache_ttl_seconds: Cache del gateway en segundos (0 la apaga)
    :param prices_path: Ruta del archivo de precios
    :param environment: ``development`` o ``production``
    :param api_keys: Mapa cliente a clave (secreto, no sale en ``repr``)
    :param rate_limit_per_minute: Peticiones por cliente por minuto
    :param pii_mode: ``mask`` enmascara y sigue; ``block`` rechaza con 422
    :param max_history_messages: Mensajes maximos en ``history``
    :param max_answer_chars: Largo maximo de la respuesta
    """

    model_provider: str
    agent_max_steps: int
    max_question_chars: int
    employees_path: str
    service_name: str = DEFAULT_SERVICE_NAME
    slo_p95_ms: int = DEFAULT_SLO_P95_MS
    langsmith_tracing: bool = False
    hide_inputs: bool = True
    hide_outputs: bool = True
    cf_account_id: str = ""
    cf_gateway_id: str = DEFAULT_CF_GATEWAY_ID
    cf_api_token: str = field(default="", repr=False)
    model_small: str = DEFAULT_MODEL_SMALL
    model_large: str = DEFAULT_MODEL_LARGE
    routing: bool = True
    router_max_chars: int = DEFAULT_ROUTER_MAX_CHARS
    history_window: int = DEFAULT_HISTORY_WINDOW
    model_max_tokens: int = DEFAULT_MODEL_MAX_TOKENS
    model_temperature: float = 0
    cache_ttl_seconds: int = 0
    prices_path: str = DEFAULT_PRICES_PATH
    environment: str = DEFAULT_ENVIRONMENT
    api_keys: Dict[str, str] = field(default_factory=dict, repr=False)
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE
    pii_mode: str = DEFAULT_PII_MODE
    max_history_messages: int = DEFAULT_MAX_HISTORY_MESSAGES
    max_answer_chars: int = DEFAULT_MAX_ANSWER_CHARS


def _read_non_negative_int(env, name, default):
    """Lee un entero mayor o igual a 0 de las variables de entorno.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param name: Nombre de la variable
    :type name: str
    :param default: Valor por omision
    :type default: int
    :return: El valor leido
    :rtype: int
    :raises ValueError: Si el valor no es un entero mayor o igual a 0
    """
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from error
    if value < 0:
        raise ValueError(f"{name} must be at least 0, got {value}")
    return value


def _read_float(env, name, default):
    """Lee un numero decimal de las variables de entorno.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param name: Nombre de la variable
    :type name: str
    :param default: Valor por omision
    :type default: float
    :return: El valor leido
    :rtype: float
    :raises ValueError: Si el valor no es un numero
    """
    raw = env.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a number, got {raw!r}") from error


def _check_gateway(env):
    """Exige las tres variables de Cloudflare cuando el proveedor es gateway.

    Nunca incluye valores en el error, solo el nombre de la variable.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :raises ValueError: Si falta alguna variable ``CF_*``
    """
    for name in ("CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN"):
        if not env.get(name, "").strip():
            raise ValueError(f"{name} is required when MODEL_PROVIDER=gateway")


def _read_bool(env, name, default):
    """Lee un booleano (``true`` o ``false``) de las variables de entorno.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param name: Nombre de la variable
    :type name: str
    :param default: Valor por omision
    :type default: bool
    :return: El valor leido
    :rtype: bool
    :raises ValueError: Si el valor no es ``true`` ni ``false``
    """
    raw = env.get(name)
    if raw is None:
        return default
    text = raw.strip().lower()
    if text not in ("true", "false"):
        raise ValueError(f"{name} must be 'true' or 'false', got {raw!r}")
    return text == "true"


def _read_positive_int(env, name, default):
    """Lee un entero positivo de las variables de entorno.

    :param env: Variables de entorno
    :type env: Mapping[str, str]
    :param name: Nombre de la variable
    :type name: str
    :param default: Valor por omision
    :type default: int
    :return: El valor leido
    :rtype: int
    :raises ValueError: Si el valor no es un entero mayor o igual a 1
    """
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from error
    if value < 1:
        raise ValueError(f"{name} must be at least 1, got {value}")
    return value


def load_config(env: Mapping[str, str]) -> Config:
    """Construye la configuracion a partir de un mapa de entorno.

    :param env: Variables de entorno (por ejemplo ``os.environ``)
    :type env: Mapping[str, str]
    :return: La configuracion validada
    :rtype: Config
    :raises ValueError: Si algun valor es invalido
    """
    environment = env.get("ENVIRONMENT", DEFAULT_ENVIRONMENT).strip().lower()
    if environment not in ENVIRONMENTS:
        raise ValueError("ENVIRONMENT must be 'development' or 'production'")
    pii_mode = env.get("PII_MODE", DEFAULT_PII_MODE).strip().lower()
    if pii_mode not in PII_MODES:
        # Sin el valor leido: solo los modos validos.
        raise ValueError("PII_MODE must be 'mask' or 'block'")
    provider = env.get("MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER)
    if provider == "gateway":
        _check_gateway(env)
    return Config(
        model_provider=provider,
        agent_max_steps=_read_positive_int(
            env, "AGENT_MAX_STEPS", DEFAULT_AGENT_MAX_STEPS
        ),
        max_question_chars=_read_positive_int(
            env, "MAX_QUESTION_CHARS", DEFAULT_MAX_QUESTION_CHARS
        ),
        employees_path=env.get("EMPLOYEES_PATH", DEFAULT_EMPLOYEES_PATH),
        service_name=env.get("SERVICE_NAME", DEFAULT_SERVICE_NAME),
        slo_p95_ms=_read_positive_int(env, "SLO_P95_MS", DEFAULT_SLO_P95_MS),
        langsmith_tracing=_read_bool(env, "LANGSMITH_TRACING", False),
        hide_inputs=_read_bool(env, "HIDE_INPUTS", True),
        hide_outputs=_read_bool(env, "HIDE_OUTPUTS", True),
        cf_account_id=env.get("CF_ACCOUNT_ID", ""),
        cf_gateway_id=env.get("CF_GATEWAY_ID", DEFAULT_CF_GATEWAY_ID),
        cf_api_token=env.get("CF_API_TOKEN", ""),
        model_small=env.get("MODEL_SMALL", DEFAULT_MODEL_SMALL),
        model_large=env.get("MODEL_LARGE", DEFAULT_MODEL_LARGE),
        routing=_read_bool(env, "ROUTING", True),
        router_max_chars=_read_positive_int(
            env, "ROUTER_MAX_CHARS", DEFAULT_ROUTER_MAX_CHARS
        ),
        history_window=_read_non_negative_int(
            env, "HISTORY_WINDOW", DEFAULT_HISTORY_WINDOW
        ),
        model_max_tokens=_read_positive_int(
            env, "MODEL_MAX_TOKENS", DEFAULT_MODEL_MAX_TOKENS
        ),
        model_temperature=_read_float(env, "MODEL_TEMPERATURE", 0),
        cache_ttl_seconds=_read_non_negative_int(env, "CACHE_TTL_SECONDS", 0),
        prices_path=env.get("PRICES_PATH", DEFAULT_PRICES_PATH),
        environment=environment,
        api_keys=parse_api_keys(env.get("API_KEYS", "")),
        rate_limit_per_minute=_read_positive_int(
            env, "RATE_LIMIT_PER_MINUTE", DEFAULT_RATE_LIMIT_PER_MINUTE
        ),
        pii_mode=pii_mode,
        max_history_messages=_read_positive_int(
            env, "MAX_HISTORY_MESSAGES", DEFAULT_MAX_HISTORY_MESSAGES
        ),
        max_answer_chars=_read_positive_int(
            env, "MAX_ANSWER_CHARS", DEFAULT_MAX_ANSWER_CHARS
        ),
    )
