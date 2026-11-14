"""Pruebas de la API con clave: rechazos, registro y trazas (S4).

Interfaz fijada para ``create_app`` y la observabilidad:

- ``create_app(config, model, directory, clock=None, rate_clock=None)``:
  ``rate_clock`` es un reloj en segundos (``float``) para el limitador.
- ``app.observability.client_var``: ``ContextVar`` con el cliente (por omision
  ``None``). ``JsonLogger.log`` agrega ``client`` a cada evento cuando existe,
  y ``tracing.traced`` lo agrega a ``metadata``.
"""

import contextvars
import json
import sys
import types

from helpers import TEST_API_KEY, TEST_CLIENT, FakeClock
from app.config import load_config
from app.observability import client_var, request_id_var
from app.tracing import setup_tracing, traced

WRONG_KEY = "wrong-key-value-123456"
QUESTION = {"question": "Who is EMP-0004?"}


def _events(raw_log):
    return [json.loads(x) for x in raw_log.splitlines() if x.startswith("{")]


def test_rejections_carry_a_request_id_are_logged_and_never_leak_the_key(
    build_client, capsys
):
    # Configuracion por omision: sin API_KEYS la API responde 401 siempre.
    closed = build_client({"API_KEYS": ""}, api_key=WRONG_KEY)
    denied = closed.post("/ask", json=QUESTION)
    assert denied.status_code == 401
    assert denied.json() == {"detail": "invalid or missing API key"}
    assert denied.headers["X-Request-ID"]
    clock = FakeClock()
    limited = build_client({"RATE_LIMIT_PER_MINUTE": "1"}, rate_clock=clock)
    assert limited.post("/ask", json=QUESTION).status_code == 200
    throttled = limited.post("/ask", json=QUESTION)
    assert throttled.status_code == 429
    assert throttled.headers["X-Request-ID"]
    assert int(throttled.headers["Retry-After"]) >= 1
    output = capsys.readouterr().out
    statuses = [e["status"] for e in _events(output) if e["event"] == "request"]
    assert 401 in statuses and 429 in statuses
    everything = output + denied.text + throttled.text
    for secret in (WRONG_KEY, TEST_API_KEY):
        assert secret not in everything


def test_trace_metadata_carries_the_client_and_never_the_key(monkeypatch):
    captured = []

    def traceable(name, run_type, client):  # pylint: disable=unused-argument
        def decorate(func):
            def wrapped(*args, langsmith_extra=None, **kwargs):
                captured.append(langsmith_extra)
                return func(*args, **kwargs)

            return wrapped

        return decorate

    fake = types.SimpleNamespace(
        Client=lambda **kwargs: object(), traceable=traceable
    )
    monkeypatch.setitem(sys.modules, "langsmith", fake)
    config = load_config({"LANGSMITH_TRACING": "true"})
    assert setup_tracing(config, {"LANGSMITH_API_KEY": "ls-secret"}) is True

    @traced("unit")
    def work():
        return "done"

    context = contextvars.copy_context()

    def run():
        request_id_var.set("req-1")
        client_var.set(TEST_CLIENT)
        return work()

    try:
        assert context.run(run) == "done"
    finally:
        setup_tracing(load_config({}), {})
    metadata = captured[0]["metadata"]
    assert metadata["client"] == TEST_CLIENT
    assert metadata["request_id"] == "req-1"
    assert TEST_API_KEY not in json.dumps(metadata)
