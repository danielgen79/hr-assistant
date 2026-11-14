"""Pasos de los escenarios Gherkin de observability.feature."""

import json
import sys
import time
import uuid

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.llm import create_model

scenarios("features/observability.feature")

QUESTION = "Who is EMP-0004?"


class ExplodingModel:
    """Modelo que falla con un error inesperado."""

    def complete(self, messages):
        raise RuntimeError("secret detail that must not reach the log")


class SlowModel:
    """Modelo simulado que tarda unos milisegundos en responder."""

    def __init__(self, inner):
        self._inner = inner

    def complete(self, messages):
        time.sleep(0.02)
        return self._inner.complete(messages)


@pytest.fixture(autouse=True)
def _capture_stdout(capsys):
    """Crea capsys antes de los pasos When, para no perder el log."""
    return capsys


@pytest.fixture(name="context")
def context_fixture():
    """Estado compartido entre los pasos de un escenario."""
    return {"env": {}, "model": None}


def _log_events(capsys, context):
    """Devuelve los eventos JSON escritos en la salida estandar."""
    context["raw_log"] = context.get("raw_log", "") + capsys.readouterr().out
    events = []
    for line in context["raw_log"].splitlines():
        if line.startswith("{"):
            events.append(json.loads(line))
    return events


def _events_named(capsys, context, name):
    return [e for e in _log_events(capsys, context) if e["event"] == name]


@given("the model fails with an unexpected error")
def given_failing_model(context):
    context["model"] = ExplodingModel()


@given("the latency target is 1 millisecond and the model is slow")
def given_slow_model(context, directory):
    context["env"]["SLO_P95_MS"] = "1"
    context["model"] = SlowModel(create_model("fake", directory))


@given("LangSmith cannot be imported")
def given_no_langsmith(monkeypatch):
    # Un valor None en sys.modules hace que "import langsmith" falle.
    monkeypatch.setitem(sys.modules, "langsmith", None)


@when(parsers.parse('I ask "{question}" without a request id'))
def when_ask_without_id(build_client, context, question):
    client = build_client(context["env"], context["model"])
    context["response"] = client.post("/ask", json={"question": question})
    context["question"] = question


@when(parsers.parse('I ask "{question}" with the request id "{request_id}"'))
def when_ask_with_id(build_client, context, question, request_id):
    client = build_client(context["env"], context["model"])
    context["response"] = client.post(
        "/ask",
        json={"question": question},
        headers={"X-Request-ID": request_id},
    )
    context["question"] = question


@when(parsers.parse('I request the health endpoint with the request id "{rid}"'))
def when_health_with_id(build_client, context, rid):
    client = build_client(context["env"])
    context["response"] = client.get("/health", headers={"X-Request-ID": rid})


@when(parsers.parse("I ask {count:d} questions"))
def when_ask_many(build_client, context, count):
    client = build_client(context["env"], context["model"])
    context["client"] = client
    for _ in range(count):
        client.post("/ask", json={"question": QUESTION})


@when("I request the metrics")
def when_metrics(context):
    context["response"] = context["client"].get("/metrics")


@when("I request the home page")
def when_home(client, context):
    context["response"] = client.get("/")


@then(parsers.parse("the response status is {status:d}"))
def then_status(context, status):
    assert context["response"].status_code == status


@then("the response header carries a generated UUID")
def then_header_is_uuid(context):
    assert uuid.UUID(context["response"].headers["X-Request-ID"])


@then(parsers.parse('the response header request id is "{request_id}"'))
def then_header_is(context, request_id):
    assert context["response"].headers["X-Request-ID"] == request_id


@then("the response body carries the same request id")
def then_body_has_same_id(context):
    response = context["response"]
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


@then(parsers.parse('the log has a request event for "{method}" "{path}" '
                    "with status {status:d}"))
def then_request_event(capsys, context, method, path, status):
    events = _events_named(capsys, context, "request")
    assert len(events) == 1
    context["event"] = events[0]
    assert (events[0]["method"], events[0]["path"]) == (method, path)
    assert events[0]["status"] == status


@then(parsers.parse('that event has a latency and the request id "{request_id}"'))
def then_event_latency_and_id(context, request_id):
    event = context["event"]
    assert event["latency_ms"] >= 0
    assert event["request_id"] == request_id


@then(parsers.parse('the log has one agent_run event with one step and the tool '
                    '"{tool}"'))
def then_agent_run(capsys, context, tool):
    runs = _events_named(capsys, context, "agent_run")
    assert len(runs) == 1
    run = runs[0]
    assert run["question_chars"] == len(context["question"])
    assert run["steps"] == 2
    assert run["tools"] == [tool]
    assert run["stopped"] is False
    assert run["input_tokens"] > 0 and run["output_tokens"] > 0
    assert run["request_id"] == "ask-1"


@then(parsers.parse('the log has one audit event for the tool "{tool}"'))
def then_audit(capsys, context, tool):
    audits = _events_named(capsys, context, "audit")
    assert len(audits) == 1
    assert audits[0]["action"] == "tool_call"
    assert audits[0]["tool"] == tool
    assert audits[0]["args"] == {"employee_id": "EMP-0004"}


@then("the log does not contain the question or the answer")
def then_log_has_no_text(capsys, context):
    _log_events(capsys, context)
    answer = context["response"].json()["answer"]
    assert context["question"] not in context["raw_log"]
    assert answer not in context["raw_log"]


@then(parsers.parse('the body says "{detail}" with the request id "{request_id}"'))
def then_error_body(context, detail, request_id):
    assert context["response"].json() == {
        "detail": detail,
        "request_id": request_id,
    }


@then("the log has an error event with only the error type")
def then_error_event(capsys, context):
    errors = _events_named(capsys, context, "error")
    assert len(errors) == 1
    assert "RuntimeError" in json.dumps(errors[0])
    assert "secret detail" not in context["raw_log"]
    requests = _events_named(capsys, context, "request")
    assert requests[0]["status"] == 500


@then(parsers.parse("the metrics show {count:d} requests and positive tokens"))
def then_metrics_counts(context, count):
    body = context["response"].json()
    assert body["requests"] >= count
    assert body["tokens"]["input"] > 0
    assert body["tokens"]["output"] > 0
    assert body["latency_ms"]["p50"] <= body["latency_ms"]["p95"]
    assert isinstance(body["pid"], int)


@then("the service level objective is met")
def then_slo_met(context):
    slo = context["response"].json()["slo"]
    assert slo["p95_ms_target"] == 2000
    assert slo["met"] is True


@then("the service level objective is not met")
def then_slo_not_met(context):
    slo = context["response"].json()["slo"]
    assert slo["p95_ms_target"] == 1
    assert slo["met"] is False


@then(parsers.parse('the page mentions "{text}"'))
def then_page_mentions(context, text):
    assert text in context["response"].text
