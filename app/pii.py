"""Deteccion y enmascarado de datos sensibles, con funciones puras.

Va por reglas (expresiones regulares y suma de Luhn): puede dar falsos
positivos y no detecta nombres propios. Nunca escribe ni devuelve el valor
encontrado, solo el marcador y el conteo por tipo.
"""

import re

# Las expresiones usan ``(?<!...)`` para empezar solo al inicio de cada tramo,
# de modo que el tiempo crece de forma lineal con el largo del texto.
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@"
    r"[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,8}"
)
_CURP = re.compile(
    r"(?<![A-Za-z0-9])[A-Z]{4}\d{6}[HM][A-Z]{5}[0-9A-Z]\d(?![A-Za-z0-9])"
)
_RFC = re.compile(r"(?<![A-Za-z0-9])[A-Z]{3,4}\d{6}[A-Z0-9]{3}(?![A-Za-z0-9])")
# Primero las formas que no son datos sensibles (fecha e id de empleado); luego
# un tramo de digitos con separadores simples, que se clasifica despues.
_NUMBERS = re.compile(
    r"(?P<skip>(?<!\w)\d{4}-\d{2}-\d{2}(?!\w)|(?<!\w)EMP-\d+)"
    r"|(?P<num>(?<!\w)(?:\+52[ -]?)?\d(?:[ -]?\d)*)"
)
_NON_DIGITS = re.compile(r"\D")

PHONE_DIGITS = 10
CLABE_DIGITS = 18
CARD_MIN_DIGITS = 13
CARD_MAX_DIGITS = 19
COUNTRY_PREFIX = "+52"


def luhn_valid(digits):
    """Revisa la suma de Luhn de un texto de digitos.

    :param digits: Texto formado solo por digitos
    :type digits: str
    :return: ``True`` si la suma es multiplo de 10
    :rtype: bool
    """
    if not digits or not digits.isdigit():
        return False
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _kind_of_number(raw):
    """Clasifica un tramo de digitos.

    :param raw: Tramo encontrado, con separadores
    :type raw: str
    :return: ``phone``, ``card``, ``clabe`` o ``None``
    :rtype: str or None
    """
    digits = _NON_DIGITS.sub("", raw)
    if raw.startswith(COUNTRY_PREFIX):
        return "phone" if len(digits) == PHONE_DIGITS + 2 else None
    size = len(digits)
    if size == PHONE_DIGITS:
        return "phone"
    if CARD_MIN_DIGITS <= size <= CARD_MAX_DIGITS and luhn_valid(digits):
        return "card"
    if size == CLABE_DIGITS:
        return "clabe"
    return None


def _replace(pattern, kind, text, counts):
    """Reemplaza cada hallazgo de un patron por su marcador y lo cuenta."""

    def marker(_match):
        counts[kind] = counts.get(kind, 0) + 1
        return f"[{kind.upper()}]"

    return pattern.sub(marker, text)


def _replace_numbers(text, counts):
    """Reemplaza telefonos, tarjetas y CLABE sin tocar fechas ni ids."""

    def marker(match):
        if match.group("skip") is not None:
            return match.group(0)
        kind = _kind_of_number(match.group("num"))
        if kind is None:
            return match.group(0)
        counts[kind] = counts.get(kind, 0) + 1
        return f"[{kind.upper()}]"

    return _NUMBERS.sub(marker, text)


def mask(text):
    """Enmascara los datos sensibles de un texto.

    :param text: Texto a revisar
    :type text: str
    :return: El texto con marcadores y el conteo por tipo
    :rtype: tuple[str, dict]
    """
    counts = {}
    masked = _replace(_EMAIL, "email", text, counts)
    masked = _replace(_CURP, "curp", masked, counts)
    masked = _replace(_RFC, "rfc", masked, counts)
    masked = _replace_numbers(masked, counts)
    return masked, counts


def merge_counts(*groups):
    """Suma varios conteos por tipo.

    :param groups: Diccionarios tipo a cantidad
    :return: Un solo diccionario con las sumas
    :rtype: dict
    """
    total = {}
    for group in groups:
        for kind, count in group.items():
            total[kind] = total.get(kind, 0) + count
    return total
