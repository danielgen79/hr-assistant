"""Pasos de los escenarios Gherkin de real_model.feature."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from real_model_helpers import INVENTED_TEXT, RealisticModel

from app.agent import SYSTEM_MESSAGE

scenarios("features/real_model.feature")

STEP_LIMIT_MESSAGE = (
    "No pude completar la respuesta. Intenta con una pregunta más concreta."
)


@pytest.fixture(name="context")
def context_fixture():
    """Estado compartido entre los pasos de un escenario."""
    return {"env": {}, "model": None}


@pytest.fixture(name="_capture_stdout", autouse=True)
def capture_stdout_fixture(capsys):
    """Crea capsys antes de los pasos When, para no perder el log."""
    return capsys


@given("a model that answers inside a code block")
def given_fenced(context):
    context["model"] = RealisticModel("fenced")


@given("a model that writes text before the JSON")
def given_prefixed(context):
    context["model"] = RealisticModel("prefixed")


@given("a model that returns the tool call followed by an invented answer")
def given_invented(context):
    context["model"] = RealisticModel("invented")


@given("a model that answers with plain text only")
def given_plain(context):
    context["model"] = RealisticModel("plain")


@given(parsers.parse("the agent is limited to {count:d} steps"))
def given_step_limit(context, count):
    context["env"]["AGENT_MAX_STEPS"] = str(count)


@when(parsers.parse('I ask "{question}" to that model'))
def when_ask_model(build_client, context, question):
    client = build_client(context["env"], model=context["model"])
    context["response"] = client.post("/ask", json={"question": question})


@when(parsers.parse('I ask "{question}" to the simulated model'))
def when_ask_simulated(build_client, context, question):
    client = build_client(context["env"])
    context["response"] = client.post("/ask", json={"question": question})


@then(parsers.parse("the response status is {status:d}"))
def then_status(context, status):
    assert context["response"].status_code == status


@then(parsers.parse('the tools used are "{tool}"'))
def then_tools_used(context, tool):
    assert context["response"].json()["tools_used"] == [tool]


@then(parsers.parse('the answer comes from the directory and mentions "{text}"'))
def then_answer_from_directory(context, text):
    assert text in context["response"].json()["answer"]


@then("the answer does not contain the invented text")
def then_no_invented_text(context):
    assert INVENTED_TEXT not in context["response"].json()["answer"]


@then("the answer is the step limit message")
def then_step_limit_message(context):
    assert context["response"].json()["answer"] == STEP_LIMIT_MESSAGE


@then(parsers.parse("the agent took {steps:d} steps"))
def then_steps(context, steps):
    assert context["response"].json()["steps"] == steps


@then("the system message is not in the response")
def then_not_in_response(context):
    assert SYSTEM_MESSAGE not in context["response"].text


@then("the system message is not in the log")
def then_not_in_log(capsys):
    output = capsys.readouterr().out
    assert output.strip()
    assert SYSTEM_MESSAGE not in output
    assert SYSTEM_MESSAGE[:40] not in output
