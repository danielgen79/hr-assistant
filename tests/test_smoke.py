"""Pruebas de ``scripts/smoke.py`` con ``httpx`` simulado.

Interfaz fijada: ``main(argv, env) -> int`` (``argv`` sin el nombre del
programa, ``env`` es un mapa; devuelve 0 si las tres comprobaciones pasan).
El modulo usa ``httpx.get(url, **kw)`` y ``httpx.post(url, headers=..., json=...,
**kw)`` a traves del atributo de modulo ``httpx``.
"""

import importlib.util
from pathlib import Path

import pytest

SMOKE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "smoke.py"
URL = "https://hr.example.test"
KEY = "smoke-secret-key-0123456789"


class FakeResponse:
    """Respuesta con solo el codigo de estado."""

    def __init__(self, status_code):
        self.status_code = status_code


class FakeHttpx:
    """Simula ``httpx`` y recuerda las llamadas."""

    HTTPError = Exception

    def __init__(self, health=200, without_key=401, with_key=200):
        self.codes = (health, without_key, with_key)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeResponse(self.codes[0])

    def post(self, url, headers=None, **_kwargs):
        self.calls.append(("POST", url, headers or {}))
        keyed = "X-API-Key" in (headers or {})
        return FakeResponse(self.codes[2] if keyed else self.codes[1])


@pytest.fixture(name="smoke")
def smoke_fixture():
    """Carga ``scripts/smoke.py`` desde su ruta."""
    spec = importlib.util.spec_from_file_location("smoke", SMOKE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_reports_ok_or_fail_for_each_check_and_hides_the_key(
    smoke, monkeypatch, capsys
):
    fake = FakeHttpx()
    monkeypatch.setattr(smoke, "httpx", fake)
    assert smoke.main([URL], {"SMOKE_API_KEY": KEY}) == 0
    output = capsys.readouterr().out
    assert output.count("[OK]") == 3
    assert "[FAIL]" not in output
    assert KEY not in output
    posts = [call for call in fake.calls if call[0] == "POST"]
    assert [call[1] for call in posts] == [f"{URL}/ask", f"{URL}/ask"]
    assert posts[1][2]["X-API-Key"] == KEY
    broken = FakeHttpx(with_key=500)
    monkeypatch.setattr(smoke, "httpx", broken)
    assert smoke.main([URL], {"SMOKE_API_KEY": KEY}) != 0
    output = capsys.readouterr().out
    assert output.count("[OK]") == 2
    assert output.count("[FAIL]") == 1


def test_smoke_fails_without_the_environment_key_and_calls_nothing(
    smoke, monkeypatch, capsys
):
    fake = FakeHttpx()
    monkeypatch.setattr(smoke, "httpx", fake)
    assert smoke.main([URL], {}) != 0
    assert "SMOKE_API_KEY" in capsys.readouterr().out
    assert len(fake.calls) == 0
