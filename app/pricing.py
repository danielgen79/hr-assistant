"""Precios por modelo y costo de cada respuesta."""

import json

MILLION = 1_000_000


def load_prices(path):
    """Carga los precios por modelo (USD por millon de tokens).

    :param path: Ruta del archivo JSON con la clave ``models``
    :type path: str
    :return: Mapa de nombre de modelo a ``{"input": ..., "output": ...}``
    :rtype: dict
    """
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["models"]


def compute_cost(prices, model_name, input_tokens, output_tokens):
    """Calcula el costo en USD de una llamada.

    :param prices: Precios devueltos por :func:`load_prices`
    :type prices: dict
    :param model_name: Nombre del modelo que respondio
    :type model_name: str
    :param input_tokens: Tokens de entrada
    :type input_tokens: int
    :param output_tokens: Tokens de salida
    :type output_tokens: int
    :return: Costo en USD
    :rtype: float
    :raises ValueError: Si el modelo no tiene precio
    """
    price = prices.get(model_name)
    if price is None:
        raise ValueError(f"No price for model {model_name!r}")
    total = input_tokens * price["input"] + output_tokens * price["output"]
    return total / MILLION
