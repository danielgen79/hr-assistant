"""Reglas de compliance que se aplican al arrancar en produccion.

Los mensajes nombran la regla, nunca el valor que la viola.
"""

import hmac

EXAMPLE_API_KEY = "demo-example-key-0000"
MIN_KEY_CHARS = 16


class ComplianceError(Exception):
    """El arranque en produccion se rechaza por reglas violadas."""


def check_production(config):
    """Devuelve las reglas de produccion que viola la configuracion.

    No mira ``config.environment``: quien llama decide cuando aplicarlas.

    :param config: Configuracion de la aplicacion
    :type config: Config
    :return: Identificadores de las reglas violadas
    :rtype: list
    """
    violations = []
    if config.model_provider == "fake":
        violations.append("model_provider_fake")
    keys = list(config.api_keys.values())
    if not keys:
        violations.append("api_keys_empty")
    if any(len(key) < MIN_KEY_CHARS for key in keys):
        violations.append("api_key_too_short")
    example = EXAMPLE_API_KEY.encode("utf-8")
    if any(hmac.compare_digest(key.encode("utf-8"), example) for key in keys):
        violations.append("example_api_key")
    if config.langsmith_tracing and not (
        config.hide_inputs and config.hide_outputs
    ):
        violations.append("traces_not_hidden")
    return violations


def enforce(config):
    """Impide arrancar en produccion con una configuracion insegura.

    :param config: Configuracion de la aplicacion
    :type config: Config
    :raises ComplianceError: Si ``ENVIRONMENT=production`` y hay violaciones
    """
    if config.environment != "production":
        return
    violations = check_production(config)
    if violations:
        raise ComplianceError(
            "production compliance failed: " + ", ".join(violations)
        )
