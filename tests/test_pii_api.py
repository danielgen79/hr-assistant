"""Pruebas de la API con datos sensibles, limites, esquema y cabeceras (S5)."""

import json

from helpers import ScriptedModel, answer_reply
from app.agent import LIMIT_MESSAGE

EMAIL = "ana.perez@example.com"
QUESTION = {"question": "Who is EMP-0004?"}


def _events(raw_log, name):
    lines = [x for x in raw_log.splitlines() if x.startswith("{")]
    return [e for e in map(json.loads, lines) if e["event"] == name]


def _ask_with_model(build_client, reply, env=None, body=None):
    model = ScriptedModel([answer_reply(reply)])
    response = build_client(env, model).post("/ask", json=body or QUESTION)
    return model, response


def test_sensitive_data_in_the_history_is_masked_before_the_model(build_client):
    history = [{"role": "user", "content": f"My email is {EMAIL}"}]
    body = {**QUESTION, "history": history}
    model, response = _ask_with_model(build_client, "ok", body=body)
    assert response.json()["pii"] == {"email": 1}
    sent = [message["content"] for message in model.calls[0]]
    assert sent[0] == "My email is [EMAIL]"
    assert EMAIL not in str(model.calls)


def test_pii_event_names_the_place_and_types_but_never_the_value(
    build_client, capsys
):
    body = {"question": f"Who is EMP-0004? Write to {EMAIL}"}
    _ask_with_model(build_client, "ok", body=body)
    output = capsys.readouterr().out
    events = _events(output, "pii_detected")
    assert [(e["where"], e["types"], e["count"]) for e in events] == [
        ("question", ["email"], 1)
    ]
    assert EMAIL not in output


def test_validation_error_does_not_echo_the_rejected_input(build_client, capsys):
    card = 4111111111111111
    history = [{"role": "user", "content": card}]
    response = build_client().post("/ask", json={**QUESTION, "history": history})
    assert response.status_code == 422
    assert str(card) not in response.text
    assert str(card) not in capsys.readouterr().out


def test_history_limits_are_exact(build_client):
    client = build_client(
        {"MAX_HISTORY_MESSAGES": "3", "MAX_QUESTION_CHARS": "10"}
    )

    def ask(count, content="x" * 10):
        history = [{"role": "user", "content": content}] * count
        return client.post("/ask", json={"question": "Hi", "history": history})

    assert ask(3).status_code == 200
    assert ask(4).status_code == 422
    assert ask(1, "x" * 11).status_code == 422


def test_a_long_answer_is_trimmed_to_the_configured_size(build_client):
    _, response = _ask_with_model(
        build_client, "a" * 200, env={"MAX_ANSWER_CHARS": "50"}
    )
    answer = response.json()["answer"]
    assert response.status_code == 200
    assert 0 < len(answer) <= 50


def test_an_empty_answer_is_replaced_by_the_limit_message(build_client):
    _, response = _ask_with_model(build_client, "")
    assert response.json()["answer"] == LIMIT_MESSAGE


def test_openapi_documents_every_field_of_the_ask_response(client):
    spec = client.get("/openapi.json").json()
    ok = spec["paths"]["/ask"]["post"]["responses"]["200"]
    schema = ok["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    expected = {
        "answer", "steps", "tools_used", "input_tokens", "output_tokens",
        "cached_calls", "cost_usd", "model", "route", "request_id", "pii",
    }
    assert expected <= set(schema["properties"])


def test_security_headers_are_set_and_sensitive_paths_are_not_cacheable(
    client, anonymous_client
):
    asked = client.post("/ask", json=QUESTION)
    metrics = client.get("/metrics")
    denied = anonymous_client.post("/ask", json=QUESTION)
    for response in (asked, metrics, denied, client.get("/health")):
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert denied.status_code == 401
    assert asked.headers["Cache-Control"] == "no-store"
    assert metrics.headers["Cache-Control"] == "no-store"


def test_metrics_count_every_sensitive_finding(client):
    before = client.get("/metrics").json()["pii_detected"]
    question = f"Who is EMP-0004? Write to {EMAIL} or call 4421234567"
    client.post("/ask", json={"question": question})
    after = client.get("/metrics").json()["pii_detected"]
    assert isinstance(after, int)
    assert after == before + 2
