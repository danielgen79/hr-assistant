"""Pruebas de config (S4), ``parse_api_keys``, ``authenticate`` y ``RateLimiter``.

Interfaz fijada para ``app/security.py``:

- ``parse_api_keys(raw) -> dict[str, str]`` (cliente a clave).
- ``authenticate(api_keys, provided) -> str | None`` (nombre del cliente).
- ``RateLimiter(limit, clock, window_seconds=60)`` con ``check(client) -> int``:
  0 si la peticion pasa; si no, los segundos de espera (entero >= 1).
"""

import pytest

from helpers import FakeClock
from app.config import load_config
from app.security import RateLimiter, authenticate, parse_api_keys

KEY_A = "key-aaaaaaaaaaaaaaaa"
KEY_B = "key-bbbbbbbbbbbbbbbb"


def test_new_settings_are_closed_by_default_and_keys_stay_out_of_repr():
    config = load_config({})
    assert config.environment == "development"
    assert config.api_keys == {}
    assert config.rate_limit_per_minute == 30
    configured = load_config(
        {"ENVIRONMENT": "production", "API_KEYS": f"hr:{KEY_A}"}
    )
    assert configured.environment == "production"
    assert configured.api_keys == {"hr": KEY_A}
    assert KEY_A not in repr(configured)


def test_api_keys_with_none_one_or_many_clients_are_parsed():
    assert len(parse_api_keys("")) == 0
    assert len(parse_api_keys("   ")) == 0
    assert parse_api_keys(f"hr:{KEY_A}") == {"hr": KEY_A}
    assert parse_api_keys(f"hr:{KEY_A},ops:{KEY_B}") == {"hr": KEY_A, "ops": KEY_B}


@pytest.mark.parametrize(
    "env, name, secret",
    [
        ({"API_KEYS": "SECRETWITHOUTCOLON"}, "API_KEYS", "SECRETWITHOUTCOLON"),
        ({"API_KEYS": "hr:"}, "API_KEYS", None),
        ({"API_KEYS": ":secretvalue0123456789"}, "API_KEYS", "secretvalue0123456789"),
        ({"API_KEYS": f"hr:{KEY_A},hr:{KEY_B}"}, "API_KEYS", KEY_B),
        ({"API_KEYS": "hr:samesecret0123456,ops:samesecret0123456"},
         "API_KEYS", "samesecret0123456"),
        ({"RATE_LIMIT_PER_MINUTE": "0"}, "RATE_LIMIT_PER_MINUTE", None),
        ({"RATE_LIMIT_PER_MINUTE": "many"}, "RATE_LIMIT_PER_MINUTE", None),
    ],
)
def test_bad_settings_stop_startup_and_never_show_the_secret(env, name, secret):
    with pytest.raises(ValueError, match=name) as raised:
        load_config(env)
    if secret:
        assert secret not in str(raised.value)


def test_authenticate_accepts_only_a_known_key_and_an_empty_map_rejects_all():
    keys = {"hr": KEY_A, "ops": KEY_B}
    assert authenticate(keys, KEY_A) == "hr"
    assert authenticate(keys, KEY_B) == "ops"
    for rejected in ("wrong", "", None, KEY_A + "x", KEY_A[:-1]):
        assert authenticate(keys, rejected) is None
    for provided in (KEY_A, "", None):
        assert authenticate({}, provided) is None


def test_rate_limiter_blocks_after_the_limit_and_recovers_with_the_clock():
    clock = FakeClock()
    limiter = RateLimiter(2, clock)
    assert limiter.check("hr") == 0
    assert limiter.check("hr") == 0
    clock.advance(10)
    wait = limiter.check("hr")
    assert isinstance(wait, int)
    assert wait == 50
    assert limiter.check("ops") == 0
    clock.advance(50)
    assert limiter.check("hr") == 0
    single = RateLimiter(1, clock)
    assert single.check("hr") == 0
    clock.advance(59.5)
    assert single.check("hr") == 1
    clock.advance(1)
    assert single.check("hr") == 0
