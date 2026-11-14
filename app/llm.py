"""Interfaz del modelo, modelo simulado determinista y fabrica."""

import json
import re
from typing import NamedTuple

import httpx

from app.directory import normalize

TOOL_RESULT_PREFIX = "Resultado de la herramienta: "
HELP_MESSAGE = "Pregúntame por un empleado (EMP-0001) o un departamento."
EMPLOYEE_ID_PATTERN = re.compile(r"EMP-\d{4}")
GATEWAY_URL = (
    "https://gateway.ai.cloudflare.com/v1/{account}/{gateway}/"
    "workers-ai/v1/chat/completions"
)
REQUEST_TIMEOUT_SECONDS = 30.0


class ModelUnavailable(Exception):
    """El modelo real no respondio o su respuesta no es valida."""


class Completion(NamedTuple):
    """Respuesta del modelo con su uso.

    :param text: Texto de la respuesta
    :param input_tokens: Tokens de entrada
    :param output_tokens: Tokens de salida
    :param cached: Si la llamada se atendio desde la cache del gateway
    """

    text: str
    input_tokens: int
    output_tokens: int
    cached: bool = False


def count_tokens(texts):
    """Cuenta tokens de forma aproximada: una palabra es un token.

    :param texts: Textos a contar
    :type texts: list
    :return: Total de palabras
    :rtype: int
    """
    return sum(len(text.split()) for text in texts)


class FakeModel:
    """Modelo simulado: decide con reglas sobre el ultimo mensaje.

    :param directory: Directorio, para conocer los departamentos
    :type directory: Directory
    """

    def __init__(self, directory):
        self._directory = directory

    def complete_with_usage(self, messages, model_name=None):
        """Responde como ``complete`` y cuenta los tokens aproximados.

        El modelo simulado responde igual con cualquier nombre; el nombre solo
        sirve para calcular el costo con su precio.

        :param messages: Conversacion como lista de mensajes
        :type messages: list
        :param model_name: Nombre del modelo simulado (no cambia la respuesta)
        :type model_name: str or None
        :return: La respuesta con su uso
        :rtype: Completion
        """
        del model_name
        text = self.complete(messages)
        input_tokens = count_tokens([m["content"] for m in messages])
        return Completion(text, input_tokens, count_tokens([text]), False)

    def complete(self, messages):
        """Responde con un unico objeto JSON segun las reglas.

        :param messages: Conversacion como lista de mensajes
        :type messages: list
        :return: Texto JSON con ``tool`` y ``args`` o con ``answer``
        :rtype: str
        """
        last = messages[-1]["content"]
        if last.startswith(TOOL_RESULT_PREFIX):
            result = last[len(TOOL_RESULT_PREFIX):]
            return self._dump({"answer": f"Según el directorio: {result}"})
        found = EMPLOYEE_ID_PATTERN.search(last)
        if found:
            return self._dump(
                {"tool": "get_employee", "args": {"employee_id": found.group()}}
            )
        normalized = normalize(last)
        for department in self._directory.departments():
            if normalize(department) in normalized:
                return self._dump(
                    {
                        "tool": "search_by_department",
                        "args": {"department": department},
                    }
                )
        return self._dump({"answer": HELP_MESSAGE})

    @staticmethod
    def _dump(payload):
        """Serializa a JSON sin escapar caracteres no ASCII."""
        return json.dumps(payload, ensure_ascii=False)


class GatewayModel:
    """Modelo real: Cloudflare Workers AI a traves de AI Gateway.

    :param account_id: Cuenta de Cloudflare
    :type account_id: str
    :param gateway_id: Gateway de Cloudflare
    :type gateway_id: str
    :param api_token: Token de Cloudflare (secreto)
    :type api_token: str
    :param max_tokens: Tope de tokens de salida
    :type max_tokens: int
    :param temperature: Temperatura del modelo
    :type temperature: float
    :param cache_ttl: Segundos de cache del gateway (0: sin encabezado)
    :type cache_ttl: int
    :param client: Cliente ``httpx.Client`` (se inyecta en las pruebas)
    :type client: httpx.Client or None
    """

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(
        self, account_id, gateway_id, api_token, max_tokens, temperature,
        cache_ttl=0, client=None,
    ):
        self._url = GATEWAY_URL.format(account=account_id, gateway=gateway_id)
        self._api_token = api_token
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._cache_ttl = cache_ttl
        self._client = client or httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)

    def complete_with_usage(self, messages, model_name):
        """Llama al gateway y devuelve texto, tokens y bandera de cache.

        :param messages: Conversacion como lista de mensajes
        :type messages: list
        :param model_name: Modelo que debe responder
        :type model_name: str
        :return: La respuesta con su uso
        :rtype: Completion
        :raises ModelUnavailable: Si la llamada falla o la respuesta es invalida
        """
        headers = {"Authorization": f"Bearer {self._api_token}"}
        if self._cache_ttl > 0:
            headers["cf-aig-cache-ttl"] = str(self._cache_ttl)
        body = {
            "model": model_name,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }
        try:
            response = self._client.post(self._url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            usage = data["usage"]
            input_tokens = int(usage["prompt_tokens"])
            output_tokens = int(usage["completion_tokens"])
        except httpx.HTTPError as error:
            # Solo el tipo del error: el mensaje podria traer datos sensibles.
            raise ModelUnavailable(
                f"gateway call failed: {type(error).__name__}"
            ) from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ModelUnavailable("gateway returned an invalid response") from None
        status = response.headers.get("cf-aig-cache-status", "")
        return Completion(
            text, input_tokens, output_tokens, status.upper() == "HIT"
        )


def create_model(provider, directory, config=None, client=None):
    """Crea el modelo segun el proveedor.

    :param provider: Nombre del proveedor (``fake`` o ``gateway``)
    :type provider: str
    :param directory: Directorio de empleados
    :type directory: Directory
    :param config: Configuracion (obligatoria con ``gateway``)
    :type config: Config or None
    :param client: Cliente HTTP para ``gateway`` (se inyecta en las pruebas)
    :type client: httpx.Client or None
    :return: Un objeto con ``complete_with_usage(messages, model_name)``
    :rtype: FakeModel or GatewayModel
    :raises ValueError: Si el proveedor es desconocido o falta la configuracion
    """
    if provider == "fake":
        return FakeModel(directory)
    if provider == "gateway":
        if config is None:
            raise ValueError("MODEL_PROVIDER gateway needs a config")
        return GatewayModel(
            account_id=config.cf_account_id,
            gateway_id=config.cf_gateway_id,
            api_token=config.cf_api_token,
            max_tokens=config.model_max_tokens,
            temperature=config.model_temperature,
            cache_ttl=config.cache_ttl_seconds,
            client=client,
        )
    raise ValueError(f"Unknown MODEL_PROVIDER (provider): {provider!r}")
