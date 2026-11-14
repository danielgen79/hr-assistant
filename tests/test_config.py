"""Pruebas de la configuracion por variables de entorno."""

import pytest

from app.config import load_config


def test_defaults_are_used_when_environment_is_empty():
    config = load_config({})
    assert config.model_provider == "fake"
    assert config.agent_max_steps == 3
    assert config.max_question_chars == 2000
    assert config.employees_path == "data/employees.json"


def test_valid_values_override_the_defaults():
    config = load_config(
        {
            "MODEL_PROVIDER": "fake",
            "AGENT_MAX_STEPS": "5",
            "MAX_QUESTION_CHARS": "100",
            "EMPLOYEES_PATH": "other.json",
        }
    )
    assert config.agent_max_steps == 5
    assert config.max_question_chars == 100
    assert str(config.employees_path) == "other.json"


def test_invalid_numbers_stop_startup_with_a_clear_message():
    for bad_value in ("0", "-2", "many"):
        with pytest.raises(ValueError, match="AGENT_MAX_STEPS"):
            load_config({"AGENT_MAX_STEPS": bad_value})
