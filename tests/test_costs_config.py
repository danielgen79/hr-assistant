"""Pruebas de la configuracion nueva de la sesion 3 (costos)."""

import pytest

from app.config import load_config
from app.llm import GatewayModel, create_model

GATEWAY_ENV = {
    "MODEL_PROVIDER": "gateway",
    "CF_ACCOUNT_ID": "account-1",
    "CF_GATEWAY_ID": "gateway-1",
    "CF_API_TOKEN": "super-secret-token-value",
}


def test_cost_settings_have_the_documented_defaults():
    config = load_config({})
    assert config.cf_account_id == ""
    assert config.cf_gateway_id == "default"
    assert config.cf_api_token == ""
    assert config.model_small == "@cf/meta/llama-3.1-8b-instruct-fast"
    assert config.model_large == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert config.routing is True
    assert config.router_max_chars == 80
    assert config.history_window == 6
    assert config.model_max_tokens == 300
    assert config.model_temperature == 0
    assert config.cache_ttl_seconds == 0
    assert config.prices_path == "data/model_prices.json"


@pytest.mark.parametrize("missing", ["CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN"])
def test_gateway_provider_needs_every_cloudflare_variable(missing):
    env = {key: value for key, value in GATEWAY_ENV.items() if key != missing}
    with pytest.raises(ValueError, match=missing):
        load_config(env)


def test_gateway_config_builds_a_model_and_hides_the_token(directory):
    config = load_config(GATEWAY_ENV)
    assert isinstance(create_model("gateway", directory, config), GatewayModel)
    assert "super-secret-token-value" not in repr(config)


@pytest.mark.parametrize(
    "name, value",
    [
        ("ROUTING", "maybe"),
        ("ROUTER_MAX_CHARS", "0"),
        ("HISTORY_WINDOW", "many"),
        ("MODEL_MAX_TOKENS", "0"),
        ("MODEL_TEMPERATURE", "hot"),
        ("CACHE_TTL_SECONDS", "-1"),
    ],
)
def test_invalid_cost_settings_are_rejected_by_name(name, value):
    with pytest.raises(ValueError, match=name):
        load_config({name: value})
