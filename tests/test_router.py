"""Pruebas del enrutador: una regla en codigo elige el modelo por pregunta."""

import pytest

from app.config import load_config
from app.router import choose_model

CONFIG = load_config({"ROUTER_MAX_CHARS": "20"})


@pytest.mark.parametrize(
    "question",
    ["Compara EMP-1", "RESUME esto", "Explica", "¿Por qué?", "Analiza", "Todos?"],
)
def test_keywords_send_the_question_to_the_large_model(question):
    assert choose_model(question, CONFIG) == (CONFIG.model_large, "keyword")


def test_question_length_decides_at_the_exact_limit():
    at_limit = "a" * 20
    assert choose_model(at_limit, CONFIG) == (CONFIG.model_small, "simple")
    assert choose_model(at_limit + "a", CONFIG) == (CONFIG.model_large, "too_long")


def test_routing_off_always_chooses_the_large_model():
    config = load_config({"ROUTING": "false"})
    assert choose_model("Hi", config) == (config.model_large, "routing_disabled")
