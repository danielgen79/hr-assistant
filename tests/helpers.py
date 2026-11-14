"""Ayudas compartidas por las pruebas del agente y de la observabilidad."""

import json

# Claves de prueba propias (S4). Ninguna es la clave de ejemplo de .env.example.
TEST_CLIENT = "hr-tester"
TEST_API_KEY = "unit-test-key-0123456789"
OTHER_CLIENT = "other-tester"
OTHER_API_KEY = "other-test-key-9876543210"
STRONG_PRODUCTION_KEY = "prod-unit-test-key-0123456789"


class FakeClock:
    """Reloj falso en segundos: se llama sin argumentos y avanza a mano."""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        """Mueve el reloj hacia adelante."""
        self.now += seconds


def production_env(**overrides):
    """Variables de entorno de una configuracion de produccion correcta.

    Usa el proveedor gateway con valores falsos y una clave fuerte de prueba.
    """
    env = {
        "ENVIRONMENT": "production",
        "MODEL_PROVIDER": "gateway",
        "CF_ACCOUNT_ID": "test-account",
        "CF_GATEWAY_ID": "test-gateway",
        "CF_API_TOKEN": "test-token",
        "API_KEYS": f"hr:{STRONG_PRODUCTION_KEY}",
        "LANGSMITH_TRACING": "false",
        "HIDE_INPUTS": "true",
        "HIDE_OUTPUTS": "true",
    }
    env.update(overrides)
    return env


class ScriptedModel:
    """Modelo de prueba: devuelve respuestas fijas y recuerda lo que recibe."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, messages):
        self.calls.append(list(messages))
        if len(self.replies) > 1:
            return self.replies.pop(0)
        return self.replies[0]


class UsageModel:
    """Modelo de prueba con conteo de tokens y bandera de cache (sesion 3).

    Cada respuesta es un ``Completion`` con tokens fijos. Recuerda el nombre
    del modelo pedido y los mensajes recibidos en cada llamada.
    """

    def __init__(self, replies, input_tokens=100, output_tokens=50, cached=()):
        self.replies = list(replies)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cached = list(cached)
        self.calls = []
        self.model_names = []

    def complete_with_usage(self, messages, model_name=None):
        """Devuelve la siguiente respuesta como ``Completion``."""
        # Importe local: el modulo app.llm lo amplia la sesion 3.
        from app.llm import Completion  # pylint: disable=import-outside-toplevel

        index = len(self.calls)
        self.calls.append(list(messages))
        self.model_names.append(model_name)
        text = self.replies[min(index, len(self.replies) - 1)]
        cached = self.cached[index] if index < len(self.cached) else False
        return Completion(text, self.input_tokens, self.output_tokens, cached)


def tool_reply(name, **args):
    """Respuesta del modelo que pide usar una herramienta."""
    return json.dumps({"tool": name, "args": args})


def answer_reply(text):
    """Respuesta final del modelo."""
    return json.dumps({"answer": text})
