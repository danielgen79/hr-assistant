"""Pasos de los escenarios Gherkin de pii.feature."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from helpers import ScriptedModel, answer_reply

scenarios("features/pii.feature")


@pytest.fixture(autouse=True)
def _capture_stdout(capsys):
    """Crea capsys antes de los pasos When, para no perder el log."""
    return capsys


@pytest.fixture(name="context")
def context_fixture():
    """Estado compartido entre los pasos de un escenario."""
    return {"env": {}, "model": None}


@given(parsers.parse('a model that answers "{text}"'))
def given_model(context, text):
    context["model"] = ScriptedModel([answer_reply(text)])


@given(parsers.parse('the sensitive data mode is "{mode}"'))
def given_mode(context, mode):
    context["env"]["PII_MODE"] = mode


@given(parsers.parse("the history limit is {count:d} messages"))
def given_history_limit(context, count):
    context["env"]["MAX_HISTORY_MESSAGES"] = str(count)


@when(parsers.parse('I ask "{question}"'))
def when_ask(build_client, context, question):
    client = build_client(context["env"], context["model"])
    context["response"] = client.post("/ask", json={"question": question})


@when(parsers.parse('I ask "{question}" with a history of {count:d} messages'))
def when_ask_with_history(build_client, context, question, count):
    client = build_client(context["env"], context["model"])
    history = [{"role": "user", "content": "hello"}] * count
    context["response"] = client.post(
        "/ask", json={"question": question, "history": history}
    )


@when("I send 20 simultaneous questions with distinct request ids")
def when_ask_concurrently(build_client, context):
    context["env"]["RATE_LIMIT_PER_MINUTE"] = "1000"
    client = build_client(context["env"], context["model"])
    context["ids"] = [f"load-{number}" for number in range(20)]

    def call(request_id):
        return client.post(
            "/ask",
            json={"question": "Who is EMP-0004?"},
            headers={"X-Request-ID": request_id},
        )

    with ThreadPoolExecutor(max_workers=20) as pool:
        context["responses"] = list(pool.map(call, context["ids"]))


@then(parsers.parse("the response status is {status:d}"))
def then_status(context, status):
    assert context["response"].status_code == status


@then(parsers.parse('the report counts {count:d} "{kind}"'))
def then_report_counts(context, count, kind):
    assert context["response"].json()["pii"] == {kind: count}


@then(parsers.parse('the model never received "{value}"'))
def then_model_never_saw(context, value):
    assert context["model"].calls
    assert value not in str(context["model"].calls)


@then("the model was not called")
def then_model_not_called(context):
    assert context["model"].calls == []


@then(parsers.parse('the response and the log never contain "{value}"'))
def then_no_leak(capsys, context, value):
    assert value not in context["response"].text
    assert value not in capsys.readouterr().out


@then(parsers.parse('the error lists the type "{kind}" and a request id'))
def then_error_lists_type(context, kind):
    body = context["response"].json()
    assert body["detail"] == "sensitive data detected"
    assert body["types"] == [kind]
    assert body["request_id"]


@then(parsers.parse('the answer is "{text}"'))
def then_answer_is(context, text):
    assert context["response"].json()["answer"] == text


@then("every response is 200 and carries its own request id")
def then_ids_are_kept(context):
    responses = context["responses"]
    assert [r.status_code for r in responses] == [200] * 20
    assert [r.headers["X-Request-ID"] for r in responses] == context["ids"]
    assert [r.json()["request_id"] for r in responses] == context["ids"]
