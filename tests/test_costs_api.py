"""Pruebas de la API con las palancas de costo: ventana, cache y variables."""

from pathlib import Path

import pytest

from helpers import UsageModel, answer_reply, tool_reply

PRODUCT_DIR = Path(__file__).resolve().parents[1]
SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"
SMALL_INPUT_PRICE = 0.045
SMALL_OUTPUT_PRICE = 0.384


def test_only_the_last_history_messages_reach_the_model(build_client):
    model = UsageModel([answer_reply("ok")])
    client = build_client({"HISTORY_WINDOW": "2"}, model)
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg-{i}"}
        for i in range(5)
    ]
    response = client.post("/ask", json={"question": "Hi", "history": history})
    assert response.status_code == 200
    sent = [message["content"] for message in model.calls[0]]
    assert sent == ["msg-3", "msg-4", "Hi"]
    assert model.model_names == [SMALL]


def test_a_cached_call_is_counted_and_costs_nothing(build_client):
    model = UsageModel(
        [tool_reply("get_employee", employee_id="EMP-0004"), answer_reply("ok")],
        input_tokens=1_000,
        output_tokens=200,
        cached=[True, False],
    )
    body = build_client(model=model).post("/ask", json={"question": "EMP-0004"}).json()
    assert body["cached_calls"] == 1
    assert body["input_tokens"] == 2_000
    expected = (1_000 * SMALL_INPUT_PRICE + 200 * SMALL_OUTPUT_PRICE) / 1_000_000
    assert body["cost_usd"] == pytest.approx(expected, abs=1e-9)


def test_env_example_lists_the_new_variables_without_secrets():
    lines = (PRODUCT_DIR / ".env.example").read_text(encoding="utf-8").splitlines()
    values = dict(
        line.split("=", 1) for line in lines if "=" in line and line[0] != "#"
    )
    for name in (
        "CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN", "MODEL_SMALL",
        "MODEL_LARGE", "ROUTING", "ROUTER_MAX_CHARS", "HISTORY_WINDOW",
        "MODEL_MAX_TOKENS", "MODEL_TEMPERATURE", "CACHE_TTL_SECONDS",
        "PRICES_PATH",
    ):
        assert name in values, name
    assert values["CF_API_TOKEN"].strip() == ""
