"""Log JSON, id de peticion y metricas del proceso."""

import contextvars
import json
import math
import os
import sys
import threading
from datetime import timezone

request_id_var = contextvars.ContextVar("request_id", default=None)
client_var = contextvars.ContextVar("client", default=None)


class JsonLogger:
    """Escribe un evento por linea, en JSON, en la salida estandar.

    :param service: Valor del campo ``service``
    :type service: str
    :param clock: Funcion sin argumentos que devuelve un ``datetime`` con zona
    :type clock: Callable
    """

    def __init__(self, service, clock):
        self._service = service
        self._clock = clock

    def log(self, event, **fields):
        """Escribe un evento.

        :param event: Nombre del evento
        :type event: str
        :param fields: Campos propios del evento
        """
        entry = {
            "ts": self._clock().astimezone(timezone.utc).isoformat(),
            "service": self._service,
            "event": event,
            "request_id": request_id_var.get(),
        }
        client = client_var.get()
        if client is not None:
            entry["client"] = client
        entry.update(fields)
        # json.dumps escapa los saltos de linea: un evento, una linea.
        line = json.dumps(entry, ensure_ascii=False, default=str)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def _percentile(sorted_values, fraction):
    """Calcula un percentil por rango mas cercano.

    :param sorted_values: Valores ordenados de menor a mayor
    :type sorted_values: list
    :param fraction: Fraccion entre 0 y 1
    :type fraction: float
    :return: El percentil, o 0 si no hay valores
    """
    if not sorted_values:
        return 0
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return sorted_values[rank - 1]


class Metrics:
    """Contadores de este proceso, seguros entre hilos."""

    def __init__(self):
        self._lock = threading.Lock()
        self._latencies = []
        self._errors = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cost_usd = 0.0

    def record_request(self, status, latency_ms):
        """Registra una peticion terminada.

        :param status: Codigo HTTP de la respuesta
        :type status: int
        :param latency_ms: Duracion en milisegundos
        :type latency_ms: float
        """
        with self._lock:
            self._latencies.append(latency_ms)
            if status >= 500:
                self._errors += 1

    def record_tokens(self, input_tokens, output_tokens):
        """Suma los tokens de una corrida del agente.

        :type input_tokens: int
        :type output_tokens: int
        """
        with self._lock:
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens

    def record_cost(self, cost_usd):
        """Suma el costo en USD de una respuesta.

        :param cost_usd: Costo de la respuesta
        :type cost_usd: float
        """
        with self._lock:
            self._cost_usd += cost_usd

    def snapshot(self, slo_p95_ms):
        """Resume el estado actual con la forma de ``GET /metrics``.

        :param slo_p95_ms: Meta de latencia p95 en milisegundos
        :type slo_p95_ms: int
        :return: Metricas del proceso
        :rtype: dict
        """
        with self._lock:
            ordered = sorted(self._latencies)
            total = len(ordered)
            p95 = _percentile(ordered, 0.95)
            return {
                "pid": os.getpid(),
                "requests": total,
                "error_rate": self._errors / total if total else 0,
                "latency_ms": {"p50": _percentile(ordered, 0.5), "p95": p95},
                "tokens": {
                    "input": self._input_tokens,
                    "output": self._output_tokens,
                },
                "cost_usd": self._cost_usd,
                "slo": {"p95_ms_target": slo_p95_ms, "met": p95 < slo_p95_ms},
            }
