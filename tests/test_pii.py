"""Pruebas unitarias de la deteccion de datos sensibles (app/pii.py).

Interfaz fijada: ``mask(text)`` devuelve ``(texto_enmascarado, conteo)`` con el
conteo por tipo (``{"email": 1}``); ``luhn_valid(digits)`` recibe un texto de
digitos y devuelve un booleano.
"""

import time

import pytest

from app.pii import luhn_valid, mask

NINETEEN_DIGIT_CARD = "4" + "1" * 17 + "0"


def test_luhn_accepts_valid_numbers_and_rejects_invalid_ones():
    assert luhn_valid("4111111111111111")
    assert luhn_valid("4222222222222")
    assert luhn_valid(NINETEEN_DIGIT_CARD)
    assert not luhn_valid("4111111111111112")


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ("ana.perez@example.com", "email"),
        ("442 123 4567", "phone"),
        ("442-123-4567", "phone"),
        ("+52 442 123 4567", "phone"),
        ("4421234567", "phone"),
        ("4111 1111 1111 1111", "card"),
        ("4222222222222", "card"),
        (NINETEEN_DIGIT_CARD, "card"),
        ("012345678901234567", "clabe"),
        ("PEGA800101HDFRRN09", "curp"),
        ("PEGA800101AB1", "rfc"),
    ],
)
def test_each_sensitive_type_is_masked_with_its_marker(value, kind):
    masked, counts = mask(f"Contact: {value} thanks")
    assert counts == {kind: 1}
    assert f"[{kind.upper()}]" in masked
    assert value not in masked
    assert masked.startswith("Contact: ") and masked.endswith(" thanks")


@pytest.mark.parametrize(
    "text",
    [
        "Who is EMP-0004?",
        "He joined on 2019-03-04",
        "The number 4111111111111112 fails the Luhn check",
        "",
    ],
)
def test_ids_dates_invalid_cards_and_empty_text_are_not_sensitive(text):
    assert mask(text) == (text, {})


def test_a_curp_is_not_also_counted_as_an_rfc():
    masked, counts = mask("PEGA800101HDFRRN09")
    assert counts == {"curp": 1}
    assert masked == "[CURP]"


def test_several_matches_are_counted_and_the_text_around_is_kept():
    masked, counts = mask("a@b.com and c@d.org call 4421234567")
    assert masked == "[EMAIL] and [EMAIL] call [PHONE]"
    assert counts == {"email": 2, "phone": 1}


def test_long_inputs_are_processed_without_catastrophic_backtracking():
    started = time.perf_counter()
    for text in ("9" * 30000, "a@" * 20000, "A" * 50000, "1234 " * 8000):
        mask(text)
    assert time.perf_counter() - started < 5
