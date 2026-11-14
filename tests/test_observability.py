"""Pruebas unitarias de la observabilidad (sesion 2).

Contrato que estas pruebas esperan de ``app.observability``:

- ``request_id_var``: ``ContextVar`` con el id de la peticion en curso.
- ``JsonLogger(service, clock)``: ``log(event, **fields)`` escribe una linea
  JSON en la salida estandar (la que haya al momento de llamar). ``clock`` es
  un callable sin argumentos que devuelve un ``datetime`` con zona horaria.
- ``Metrics()``: ``record_request(status, latency_ms)``,
  ``record_tokens(input_tokens, output_tokens)`` y
  ``snapshot(slo_p95_ms)`` con la forma de ``GET /metrics``.
"""

import contextvars
import json
from datetime import datetime, timezone

import pytest
from helpers import ScriptedModel, answer_reply, tool_reply

from app.agent import Agent
from app.config import load_config
from app.observability import JsonLogger, Metrics, request_id_var

FIXED_TIME = datetime(2026, 11, 7, 15, 30, 0, tzinfo=timezone.utc)


def _recorder_for(events):
    def record(event, **fields):
        events.append({"event": event, **fields})

    return record


_tool = tool_reply
_answer = answer_reply


def test_new_settings_have_safe_defaults():
    config = load_config({})
    assert config.service_name == "hr-assistant"
    assert config.slo_p95_ms == 2000
    assert config.langsmith_tracing is False
    assert config.hide_inputs is True
    assert config.hide_outputs is True


@pytest.mark.parametrize(
    "name, value",
    [
        ("SLO_P95_MS", "0"),
        ("SLO_P95_MS", "fast"),
        ("HIDE_INPUTS", "maybe"),
        ("HIDE_OUTPUTS", "2"),
        ("LANGSMITH_TRACING", "yes please"),
    ],
)
def test_invalid_new_settings_stop_startup(name, value):
    with pytest.raises(ValueError, match=name):
        load_config({name: value})


def test_api_key_never_appears_in_the_configuration_text():
    config = load_config({"LANGSMITH_API_KEY": "lsv2-super-secret"})
    assert "lsv2-super-secret" not in repr(config)


def test_log_line_is_one_json_object_with_the_required_fields(capsys):
    logger = JsonLogger("hr-assistant", lambda: FIXED_TIME)
    context = contextvars.copy_context()
    context.run(request_id_var.set, "req-1")
    context.run(logger.log, "request", method="GET", path="/health")
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["service"] == "hr-assistant"
    assert entry["event"] == "request"
    assert entry["request_id"] == "req-1"
    assert entry["path"] == "/health"
    parsed = datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
    assert parsed == FIXED_TIME


def test_log_escapes_line_breaks_so_one_event_stays_on_one_line(capsys):
    logger = JsonLogger("hr-assistant", lambda: FIXED_TIME)
    logger.log("audit", args={"department": "line\nbreak"})
    assert len(capsys.readouterr().out.strip().splitlines()) == 1


def test_request_id_is_isolated_between_contexts():
    context = contextvars.copy_context()
    context.run(request_id_var.set, "only-inside")
    assert request_id_var.get(None) != "only-inside"


def test_percentiles_for_empty_single_and_several_latencies():
    metrics = Metrics()
    empty = metrics.snapshot(2000)
    assert empty["requests"] == 0
    assert empty["error_rate"] == 0
    assert empty["latency_ms"] == {"p50": 0, "p95": 0}

    metrics.record_request(200, 7)
    assert metrics.snapshot(2000)["latency_ms"] == {"p50": 7, "p95": 7}

    other = Metrics()
    for latency in (40, 10, 30, 20):
        other.record_request(200, latency)
    assert other.snapshot(2000)["latency_ms"] == {"p50": 20, "p95": 40}


def test_error_rate_counts_only_server_errors_and_tokens_add_up():
    metrics = Metrics()
    for status in (200, 422, 404, 500):
        metrics.record_request(status, 5)
    metrics.record_tokens(3, 2)
    metrics.record_tokens(4, 1)
    snapshot = metrics.snapshot(2000)
    assert snapshot["requests"] == 4
    assert snapshot["error_rate"] == pytest.approx(0.25)
    assert snapshot["tokens"] == {"input": 7, "output": 3}
    assert isinstance(snapshot["pid"], int)


def test_slo_is_met_only_when_p95_is_strictly_below_the_target():
    metrics = Metrics()
    metrics.record_request(200, 100)
    assert metrics.snapshot(101)["slo"] == {"p95_ms_target": 101, "met": True}
    assert metrics.snapshot(100)["slo"] == {"p95_ms_target": 100, "met": False}


def test_agent_emits_one_audit_per_tool_call_without_user_text(directory):
    events = []
    model = ScriptedModel(
        [
            _tool("get_employee", employee_id="EMP-0004"),
            _tool("search_by_department", department="Ventas"),
            _answer("Listo"),
        ]
    )
    agent = Agent(model, directory, 5, _recorder_for(events))
    agent.run("a private question text")
    audits = [e for e in events if e["event"] == "audit"]
    assert [a["tool"] for a in audits] == ["get_employee", "search_by_department"]
    assert all(a["action"] == "tool_call" for a in audits)
    assert audits[0]["args"] == {"employee_id": "EMP-0004"}
    assert "a private question text" not in json.dumps(events)


def test_agent_audits_a_tool_call_for_an_unknown_employee_id(directory):
    events = []
    model = ScriptedModel(
        [_tool("get_employee", employee_id="EMP-9999"), _answer("No existe")]
    )
    Agent(model, directory, 3, _recorder_for(events)).run("Who is EMP-9999?")
    audits = [e for e in events if e["event"] == "audit"]
    assert len(audits) == 1
    assert audits[0]["args"] == {"employee_id": "EMP-9999"}


def test_agent_emits_no_audit_when_no_tool_is_called(directory):
    events = []
    agent = Agent(ScriptedModel([_answer("Hola")]), directory, 3,
                  _recorder_for(events))
    agent.run("Hi")
    assert not [e for e in events if e["event"] == "audit"]
