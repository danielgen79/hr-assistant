"""Pruebas del modelo simulado y su fabrica."""

import json

import pytest

from app.llm import create_model


def _ask(model, text):
    return json.loads(model.complete([{"role": "user", "content": text}]))


@pytest.fixture(name="model")
def model_fixture(directory):
    return create_model("fake", directory)


def test_fake_model_rules_follow_their_priority(model):
    tool_result = "Resultado de la herramienta: Jorge Díaz EMP-0004"
    assert _ask(model, tool_result) == {
        "answer": "Según el directorio: Jorge Díaz EMP-0004"
    }
    by_id = _ask(model, "EMP-0002 de Finanzas")
    assert by_id == {"tool": "get_employee", "args": {"employee_id": "EMP-0002"}}
    by_department = _ask(model, "Who is in Finanzas?")
    assert by_department["tool"] == "search_by_department"
    assert by_department["args"] == {"department": "Finanzas"}


def test_fake_model_suggests_help_when_nothing_matches(model):
    assert _ask(model, "Hello there") == {
        "answer": "Pregúntame por un empleado (EMP-0001) o un departamento."
    }


def test_unknown_provider_is_rejected(directory):
    with pytest.raises(ValueError, match="MODEL_PROVIDER|provider"):
        create_model("openai", directory)
