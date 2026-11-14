"""Pasos de los escenarios Gherkin de production.feature."""

import json
import re

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from helpers import (
    OTHER_API_KEY, TEST_API_KEY, FakeClock, ScriptedModel, answer_reply,
    production_env,
)

scenarios("features/production.feature")

QUESTION_PATH = "/ask"


@pytest.fixture(autouse=True)
def _capture_stdout(capsys):
    """Crea capsys antes de los pasos When, para no perder el log."""
    return capsys


@pytest.fixture(name="context")
def context_fixture():
    """Estado compartido entre los pasos de un escenario."""
    return {"env": {}, "clock": None, "error": None, "raw_log": ""}


def _send(build_client, context, path, key, payload=None):
    """Envia una peticion; el cliente se crea la primera vez que se usa.

    Con ``payload`` es un POST; sin el, un GET.
    """
    method = "POST" if payload is not None else "GET"
    if "client" not in context:
        context["client"] = build_client(
            context["env"], api_key=None, rate_clock=context["clock"]
        )
    headers = {"X-API-Key": key} if key else {}
    response = context["client"].request(
        method, path, json=payload, headers=headers
    )
    context["response"] = response
    return response


def _events(capsys, context):
    context["raw_log"] += capsys.readouterr().out
    return [
        json.loads(line)
        for line in context["raw_log"].splitlines()
        if line.startswith("{")
    ]


@given(parsers.parse('the environment is "{value}"'))
def given_environment(context, value):
    context["env"]["ENVIRONMENT"] = value


@given("no API keys are configured")
def given_no_keys(context):
    context["env"]["API_KEYS"] = ""


@given(parsers.parse('the environment variable {name} is "{value}"'))
def given_variable(context, name, value):
    context["env"][name] = value


@given(parsers.parse("the rate limit is {count:d} per minute"))
def given_rate_limit(context, count):
    context["env"]["RATE_LIMIT_PER_MINUTE"] = str(count)


@given("the clock is fake")
def given_fake_clock(context):
    context["clock"] = FakeClock()


@given("the production settings")
def given_production(context):
    context["env"].update(production_env())


@when(parsers.parse('I ask "{question}" with the test key'))
def when_ask_with_test_key(build_client, context, question):
    _send(build_client, context, QUESTION_PATH, TEST_API_KEY,
          {"question": question})


@when(parsers.parse('I ask "{question}" with the other key'))
def when_ask_with_other_key(build_client, context, question):
    _send(build_client, context, QUESTION_PATH, OTHER_API_KEY,
          {"question": question})


@when(parsers.parse('I ask "{question}" without a key'))
def when_ask_without_key(build_client, context, question):
    _send(build_client, context, QUESTION_PATH, None,
          {"question": question})


@when(parsers.parse('I ask "{question}" with the key "{key}"'))
def when_ask_with_key(build_client, context, question, key):
    _send(build_client, context, QUESTION_PATH, key,
          {"question": question})


@when("I request the metrics without a key")
def when_metrics_without_key(build_client, context):
    _send(build_client, context, "/metrics", None)


@when("I request the metrics with the test key")
def when_metrics_with_key(build_client, context):
    _send(build_client, context, "/metrics", TEST_API_KEY)


@when(parsers.parse('I request "{path}" without a key'))
def when_request_path(build_client, context, path):
    _send(build_client, context, path, None)


@when(parsers.parse("the clock advances {seconds:d} seconds"))
def when_clock_advances(context, seconds):
    context["clock"].advance(seconds)


@when("I start the app")
def when_start_app(build_client, context):
    model = ScriptedModel([answer_reply("ok")])
    try:
        context["client"] = build_client(
            context["env"], model=model, api_key=None
        )
    except Exception as error:  # pylint: disable=broad-exception-caught
        context["error"] = error


@then(parsers.parse("the response status is {status:d}"))
def then_status(context, status):
    assert context["response"].status_code == status


@then(parsers.parse('the body detail is "{detail}"'))
def then_detail(context, detail):
    assert context["response"].json() == {"detail": detail}


@then("the Retry-After header is a whole number of seconds")
def then_retry_after(context):
    value = context["response"].headers["Retry-After"]
    assert value.isdigit()
    assert int(value) >= 1


@then(parsers.parse('the request event in the log has the client "{name}"'))
def then_request_event_client(capsys, context, name):
    requests = [e for e in _events(capsys, context) if e["event"] == "request"]
    assert [e["client"] for e in requests if e["path"] == "/ask"] == [name]


@then(parsers.parse('the agent_run and audit events have the client "{name}"'))
def then_run_and_audit_client(capsys, context, name):
    events = _events(capsys, context)
    for kind in ("agent_run", "audit"):
        found = [e for e in events if e["event"] == kind]
        assert found, kind
        assert all(e["client"] == name for e in found)


@then("the log does not contain the test key")
def then_log_has_no_key(capsys, context):
    _events(capsys, context)
    assert TEST_API_KEY not in context["raw_log"]


@then(parsers.parse('startup is refused naming the rule "{rule}"'))
def then_refused_by_rule(context, rule):
    assert context["error"] is not None
    assert rule in str(context["error"])


@then(parsers.parse('startup is refused mentioning "{text}"'))
def then_refused_mentioning(context, text):
    assert isinstance(context["error"], ValueError)
    assert text in str(context["error"])


@then(parsers.parse("the error names entry {index:d} and length {length:d}"))
def then_error_entry_and_length(context, index, length):
    message = str(context["error"])
    assert f"entry {index}" in message
    assert f"length {length}" in message


@then(parsers.parse('the error does not contain "{text}"'))
def then_error_hides(context, text):
    assert context["error"] is not None
    assert text not in str(context["error"])


@then("the app starts")
def then_app_starts(context):
    assert context["error"] is None
    assert context["client"].get("/health").status_code == 200


@then(parsers.parse('the page has a password field with the test id "{test_id}"'))
def then_page_password_field(context, test_id):
    tags = re.findall(r"<input[^>]*>", context["response"].text)
    fields = [tag for tag in tags if f'data-testid="{test_id}"' in tag]
    assert fields
    assert 'type="password"' in fields[0]


@then("the page uses sessionStorage and never localStorage")
def then_page_storage(context):
    html = context["response"].text
    assert "sessionStorage" in html
    assert "localStorage" not in html
