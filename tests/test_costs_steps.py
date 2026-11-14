"""Pasos de los escenarios Gherkin de costs.feature."""

import json
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/costs.feature")

PRICES_FILE = Path(__file__).resolve().parents[2] / "spec" / "model_prices.json"
MILLION = 1_000_000


class UnavailableModel:
    """Modelo que siempre falla como lo haria el gateway caido."""

    def complete(self, _messages):
        # Importe local: ModelUnavailable lo crea la sesion 3.
        from app.llm import ModelUnavailable  # pylint: disable=C0415

        raise ModelUnavailable("gateway down")


@pytest.fixture(name="context")
def context_fixture():
    """Estado compartido entre los pasos de un escenario."""
    return {"env": {}, "model": None, "responses": []}


def _post(build_client, context, question):
    client = context.get("client")
    if client is None:
        client = build_client(context["env"], context["model"])
        context["client"] = client
    response = client.post("/ask", json={"question": question})
    context["responses"].append(response)
    context["response"] = response
    return response


@given(parsers.parse('the environment variable ROUTING is "{value}"'))
def given_routing(context, value):
    context["env"]["ROUTING"] = value


@given("the model is unavailable")
def given_unavailable(context):
    context["model"] = UnavailableModel()


@when(parsers.parse('I ask "{question}"'))
def when_ask(build_client, context, question):
    _post(build_client, context, question)


@when(parsers.parse('I ask "{first}" and then "{second}"'))
def when_ask_twice(build_client, context, first, second):
    _post(build_client, context, first)
    _post(build_client, context, second)


@when("I request the metrics")
def when_metrics(context):
    context["metrics"] = context["client"].get("/metrics").json()


@then(parsers.parse("the response status is {status:d}"))
def then_status(context, status):
    assert context["response"].status_code == status


@then(parsers.parse('the response model is "{model}"'))
def then_model(context, model):
    assert context["response"].json()["model"] == model


@then(parsers.parse('the route is "{route}"'))
def then_route(context, route):
    assert context["response"].json()["route"] == route


@then("the cost matches the price of that model")
def then_cost_matches_price(context):
    body = context["response"].json()
    price = json.loads(PRICES_FILE.read_text(encoding="utf-8"))["models"][
        body["model"]
    ]
    expected = (
        body["input_tokens"] * price["input"]
        + body["output_tokens"] * price["output"]
    ) / MILLION
    assert expected > 0
    assert body["cost_usd"] == pytest.approx(expected, abs=1e-9)


@then("the metrics cost equals the sum of both answer costs")
def then_metrics_cost(context):
    total = sum(r.json()["cost_usd"] for r in context["responses"])
    assert total > 0
    assert context["metrics"]["cost_usd"] == pytest.approx(total, abs=1e-9)


@then(parsers.parse('the body says "{detail}" with the request id of the response'))
def then_error_body(context, detail):
    response = context["response"]
    assert response.json() == {
        "detail": detail,
        "request_id": response.headers["X-Request-ID"],
    }
