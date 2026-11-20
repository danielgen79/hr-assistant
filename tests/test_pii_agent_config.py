"""Pruebas de la auditoria, la configuracion y las metricas de S5."""

import threading

import pytest

from helpers import ScriptedModel, answer_reply, tool_reply
from app.agent import Agent
from app.config import load_config
from app.observability import Metrics


def _audit_args(directory, tool, **args):
    """Corre el agente con una herramienta y devuelve los args auditados."""
    events = []

    def log(event, **fields):
        events.append((event, fields))

    model = ScriptedModel([tool_reply(tool, **args), answer_reply("ok")])
    Agent(model, directory, 3, log).run("question")
    audits = [fields for event, fields in events if event == "audit"]
    assert len(audits) == 1
    return audits[0]["args"]


def test_audit_keeps_only_the_arguments_the_tool_knows(directory):
    extra = {"note": "ana.perez@example.com"}
    by_id = _audit_args(directory, "get_employee", employee_id="EMP-0004", **extra)
    by_department = _audit_args(
        directory, "search_by_department", department="Engineering", **extra
    )
    assert by_id == {"employee_id": "EMP-0004"}
    assert by_department == {"department": "Engineering"}


def test_audit_arguments_are_masked_and_at_most_64_characters(directory):
    masked = _audit_args(
        directory, "get_employee", employee_id="ana.perez@example.com"
    )
    long = _audit_args(directory, "get_employee", employee_id="x" * 100)
    assert masked == {"employee_id": "[EMAIL]"}
    assert 0 < len(long["employee_id"]) <= 64


def test_sensitive_data_settings_have_safe_defaults():
    config = load_config({})
    assert config.pii_mode == "mask"
    assert config.max_history_messages == 20
    assert config.max_answer_chars == 4000


@pytest.mark.parametrize(
    "env",
    [
        {"PII_MODE": "secret-mode-xyz"},
        {"PII_MODE": "off"},
        {"MAX_HISTORY_MESSAGES": "0"},
        {"MAX_HISTORY_MESSAGES": "many"},
        {"MAX_ANSWER_CHARS": "0"},
        {"MAX_ANSWER_CHARS": "long"},
    ],
)
def test_invalid_sensitive_data_settings_are_rejected(env):
    with pytest.raises(ValueError) as error:
        load_config(env)
    if "PII_MODE" in env:
        assert env["PII_MODE"] not in str(error.value)


def test_pii_counter_is_safe_between_threads_and_starts_at_zero():
    metrics = Metrics()
    assert metrics.snapshot(2000)["pii_detected"] == 0

    def work():
        for _ in range(100):
            metrics.record_pii(1)

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert metrics.snapshot(2000)["pii_detected"] == 800
