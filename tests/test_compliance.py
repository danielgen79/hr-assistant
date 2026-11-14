"""Pruebas de compliance como codigo y del archivo ``.env.example``.

Interfaz fijada para ``app/compliance.py``:

- ``EXAMPLE_API_KEY = "demo-example-key-0000"``.
- ``check_production(config) -> list[str]``: reglas violadas, sin mirar
  ``config.environment``. Identificadores: ``model_provider_fake``,
  ``api_keys_empty``, ``api_key_too_short`` (menos de 16 caracteres),
  ``example_api_key`` y ``traces_not_hidden``.
- ``ComplianceError(Exception)``: ``create_app`` la lanza con
  ``ENVIRONMENT=production`` si hay reglas violadas. El mensaje nombra las
  reglas y nunca los valores.
"""

from pathlib import Path

import pytest

from helpers import ScriptedModel, answer_reply, production_env
from app.compliance import EXAMPLE_API_KEY, ComplianceError, check_production
from app.config import load_config

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


@pytest.mark.parametrize(
    "rule, overrides",
    [
        ("model_provider_fake", {"MODEL_PROVIDER": "fake"}),
        ("api_keys_empty", {"API_KEYS": ""}),
        ("api_key_too_short", {"API_KEYS": "hr:" + "k" * 15}),
        ("example_api_key", {"API_KEYS": f"hr:{EXAMPLE_API_KEY}"}),
        ("traces_not_hidden",
         {"LANGSMITH_TRACING": "true", "HIDE_INPUTS": "false"}),
        ("traces_not_hidden",
         {"LANGSMITH_TRACING": "true", "HIDE_OUTPUTS": "false"}),
    ],
)
def test_each_production_rule_is_reported_on_its_own(rule, overrides):
    config = load_config(production_env(**overrides))
    assert check_production(config) == [rule]


def test_compliant_settings_pass_and_violations_add_up():
    assert len(check_production(load_config(production_env()))) == 0
    sixteen = production_env(API_KEYS="hr:" + "k" * 16)
    assert len(check_production(load_config(sixteen))) == 0
    unhidden_but_off = production_env(HIDE_INPUTS="false")
    assert len(check_production(load_config(unhidden_but_off))) == 0
    both = production_env(MODEL_PROVIDER="fake", API_KEYS="")
    rules = check_production(load_config(both))
    assert sorted(rules) == ["api_keys_empty", "model_provider_fake"]


def test_example_key_is_refused_in_production_and_accepted_in_development(
    build_client,
):
    model = ScriptedModel([answer_reply("ok")])
    api_keys = f"demo:{EXAMPLE_API_KEY}"
    with pytest.raises(ComplianceError, match="example_api_key") as raised:
        build_client(production_env(API_KEYS=api_keys), model=model)
    assert EXAMPLE_API_KEY not in str(raised.value)
    development = build_client(
        {"ENVIRONMENT": "development", "API_KEYS": api_keys},
        api_key=EXAMPLE_API_KEY,
    )
    response = development.post("/ask", json={"question": "Who is EMP-0004?"})
    assert response.status_code == 200


def test_env_example_carries_the_warned_example_key_and_production_refuses_it():
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    values = dict(
        line.split("=", 1) for line in lines if "=" in line and line[0] != "#"
    )
    assert values["API_KEYS"] == "demo:demo-example-key-0000"
    assert values["ENVIRONMENT"] == "development"
    assert values["RATE_LIMIT_PER_MINUTE"] == "30"
    assert len(EXAMPLE_API_KEY) >= 16
    position = lines.index("API_KEYS=demo:demo-example-key-0000")
    comment = []
    for line in reversed(lines[:position]):
        if not line.startswith("#"):
            break
        comment.append(line)
    warning = " ".join(comment)
    assert "NUNCA" in warning
    assert "producción" in warning
    assert values["CF_API_TOKEN"].strip() == ""
    assert values["LANGSMITH_API_KEY"].strip() == ""
    config = load_config({**values, "ENVIRONMENT": "production"})
    assert "example_api_key" in check_production(config)
