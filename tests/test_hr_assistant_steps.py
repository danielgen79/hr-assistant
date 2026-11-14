"""Pasos de los escenarios Gherkin de hr_assistant.feature."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/hr_assistant.feature")

STEP_LIMIT_MESSAGE = (
    "No pude completar la respuesta. Intenta con una pregunta más concreta."
)


@pytest.fixture(name="context")
def context_fixture():
    """Estado compartido entre los pasos de un escenario."""
    return {"env": {}}


@given(parsers.parse("the agent is limited to {count:d} step"))
def given_step_limit(context, count):
    context["env"]["AGENT_MAX_STEPS"] = str(count)


@when(parsers.parse('I ask "{question}"'))
def when_ask(context, build_client, question):
    client = build_client(context["env"])
    context["client"] = client
    context["response"] = client.post("/ask", json={"question": question})


@when("I ask an empty question")
def when_ask_empty(build_client, context):
    client = build_client(context["env"])
    context["response"] = client.post("/ask", json={"question": ""})


@when("I ask a question longer than the limit")
def when_ask_too_long(build_client, context):
    client = build_client({"MAX_QUESTION_CHARS": "20"})
    context["response"] = client.post("/ask", json={"question": "a" * 21})


@when(parsers.parse('I ask "{question}" with a previous conversation'))
def when_ask_with_history(build_client, context, question):
    client = build_client(context["env"])
    history = [
        {"role": "user", "content": "Who is EMP-0002?"},
        {"role": "assistant", "content": "Según el directorio: Luis Pérez"},
    ]
    context["client"] = client
    context["question"] = question
    context["response"] = client.post(
        "/ask", json={"question": question, "history": history}
    )


@when("I request the health endpoint")
def when_health(client, context):
    context["response"] = client.get("/health")


@when("I request the home page")
def when_home(client, context):
    context["response"] = client.get("/")


@then(parsers.parse("the response status is {status:d}"))
def then_status(context, status):
    assert context["response"].status_code == status


@then(parsers.parse('the answer mentions "{text}"'))
def then_answer_mentions(context, text):
    assert text in context["response"].json()["answer"]


@then("the answer says the employee does not exist")
def then_not_exist(context):
    answer = context["response"].json()["answer"].lower()
    assert "no existe" in answer or "no encontr" in answer


@then(parsers.parse('the tools used are "{tool}"'))
def then_tools_used(context, tool):
    assert context["response"].json()["tools_used"] == [tool]


@then("no tools were used")
def then_no_tools(context):
    assert context["response"].json()["tools_used"] == []


@then(parsers.parse("the agent took {steps:d} steps"))
def then_steps(context, steps):
    assert context["response"].json()["steps"] == steps


@then("the answer is the step limit message")
def then_step_limit_message(context):
    assert context["response"].json()["answer"] == STEP_LIMIT_MESSAGE


@then("the same question without history gives the same answer")
def then_history_not_stored(context):
    client = context["client"]
    first = context["response"].json()["answer"]
    again = client.post("/ask", json={"question": context["question"]})
    assert again.json()["answer"] == first
    assert "Luis Pérez" not in again.json()["answer"]


@then(parsers.parse('the health body has status "{status}" and a numeric pid'))
def then_health_body(context, status):
    body = context["response"].json()
    assert body["status"] == status
    assert isinstance(body["pid"], int)


@then(
    parsers.parse(
        'the page contains the test ids "{first}", "{second}" and "{third}"'
    )
)
def then_page_test_ids(context, first, second, third):
    html = context["response"].text
    for test_id in (first, second, third):
        assert f'data-testid="{test_id}"' in html
