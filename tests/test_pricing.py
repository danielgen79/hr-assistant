"""Pruebas de la carga de precios y del calculo del costo."""

import json
from pathlib import Path

import pytest

from app.pricing import compute_cost, load_prices

PRODUCT_DIR = Path(__file__).resolve().parents[1]
SPEC_PRICES = PRODUCT_DIR.parent / "spec" / "model_prices.json"
SMALL = "@cf/meta/llama-3.1-8b-instruct-fast"


def test_cost_is_priced_per_million_tokens(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(
        json.dumps({"models": {"m": {"input": 2.0, "output": 10.0}}}),
        encoding="utf-8",
    )
    prices = load_prices(str(path))
    # 500 mil tokens de entrada y 100 mil de salida.
    assert compute_cost(prices, "m", 500_000, 100_000) == pytest.approx(2.0)
    assert compute_cost(prices, "m", 0, 0) == 0


def test_unknown_model_has_no_price():
    prices = {"m": {"input": 1.0, "output": 1.0}}
    with pytest.raises(ValueError, match="other-model"):
        compute_cost(prices, "other-model", 10, 10)


def test_product_prices_are_a_copy_of_the_spec_prices():
    shipped = json.loads(
        (PRODUCT_DIR / "data" / "model_prices.json").read_text(encoding="utf-8")
    )
    assert load_prices(str(PRODUCT_DIR / "data" / "model_prices.json"))[SMALL] == {
        "input": 0.045,
        "output": 0.384,
    }
    # El repositorio del producto no incluye la carpeta spec.
    if not SPEC_PRICES.exists():
        pytest.skip("spec/model_prices.json no existe en este repositorio")
    original = json.loads(SPEC_PRICES.read_text(encoding="utf-8"))
    assert shipped["models"] == original["models"]
