"""Pruebas de las reglas de S4 que la API y la configuracion deben cumplir."""

import re
from pathlib import Path

import pytest

from helpers import (
    OTHER_API_KEY, TEST_API_KEY, FakeClock, ScriptedModel, answer_reply,
    production_env,
)
from app.compliance import ComplianceError
from app.config import load_config
from app.security import parse_api_keys

QUESTION = {"question": "Who is EMP-0004?"}
CHECKLIST = Path(__file__).resolve().parents[1] / "doc" / "compliance-checklist.md"


@pytest.mark.parametrize(
    "bad_key",
    ["", TEST_API_KEY[:-1], TEST_API_KEY + "x", TEST_API_KEY.upper()],
)
def test_near_miss_keys_are_rejected_on_both_protected_routes(
    build_client, bad_key
):
    client = build_client(api_key=None)
    headers = {"X-API-Key": bad_key}
    asked = client.post("/ask", json=QUESTION, headers=headers)
    metrics = client.get("/metrics", headers=headers)
    assert asked.status_code == 401
    assert metrics.status_code == 401
    assert metrics.json() == {"detail": "invalid or missing API key"}


def test_other_client_key_reaches_the_metrics(build_client):
    client = build_client(api_key=OTHER_API_KEY)
    assert client.get("/metrics").status_code == 200


def test_retry_after_tells_the_seconds_that_are_left(build_client):
    clock = FakeClock()
    client = build_client({"RATE_LIMIT_PER_MINUTE": "1"}, rate_clock=clock)
    assert client.post("/ask", json=QUESTION).status_code == 200
    clock.advance(20)
    blocked = client.post("/ask", json=QUESTION)
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "40"


def test_public_routes_stay_open_in_a_production_configuration(build_client):
    model = ScriptedModel([answer_reply("ok")])
    client = build_client(production_env(), model=model, api_key=None)
    for path in ("/", "/health", "/docs"):
        assert client.get(path).status_code == 200, path
    assert client.post("/ask", json=QUESTION).status_code == 401


def test_rate_limit_setting_accepts_a_number_and_rejects_a_negative():
    assert load_config({"RATE_LIMIT_PER_MINUTE": "5"}).rate_limit_per_minute == 5
    with pytest.raises(ValueError, match="RATE_LIMIT_PER_MINUTE"):
        load_config({"RATE_LIMIT_PER_MINUTE": "-3"})


def test_malformed_entry_error_gives_position_and_length_never_the_value():
    with pytest.raises(ValueError) as raised:
        parse_api_keys("hr:aaaaaaaaaaaaaaaa,NOCOLONSECRET")
    message = str(raised.value)
    assert "entry 2" in message
    assert "length 13" in message
    assert "NOCOLONSECRET" not in message


@pytest.mark.parametrize(
    "overrides, rule",
    [
        ({"MODEL_PROVIDER": "fake"}, "model_provider_fake"),
        ({"API_KEYS": ""}, "api_keys_empty"),
        ({"API_KEYS": "hr:" + "k" * 15}, "api_key_too_short"),
        ({"LANGSMITH_TRACING": "true", "HIDE_OUTPUTS": "false"},
         "traces_not_hidden"),
    ],
)
def test_production_refuses_each_unsafe_setting_before_serving(
    build_client, overrides, rule
):
    model = ScriptedModel([answer_reply("ok")])
    with pytest.raises(ComplianceError, match=rule):
        build_client(production_env(**overrides), model=model)


def test_production_accepts_a_key_of_exactly_16_characters(build_client):
    model = ScriptedModel([answer_reply("ok")])
    env = production_env(API_KEYS="hr:" + "k" * 16)
    client = build_client(env, model=model, api_key=None)
    assert client.get("/health").status_code == 200


def test_checklist_rows_point_to_files_that_exist():
    root = CHECKLIST.parents[1]
    text = CHECKLIST.read_text(encoding="utf-8")
    paths = re.findall(r"`((?:app|tests)/[\w./-]+)`", text)
    assert len(paths) >= 5
    for path in paths:
        assert (root / path).is_file(), path
