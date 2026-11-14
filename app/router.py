"""Enrutador: una regla en codigo elige el modelo por pregunta."""

KEYWORDS = ("compara", "resume", "explica", "por qué", "analiza", "todos")


def choose_model(question, config):
    """Elige el modelo para una pregunta.

    :param question: Texto de la pregunta
    :type question: str
    :param config: Configuracion de la aplicacion
    :type config: Config
    :return: Nombre del modelo y motivo (``routing_disabled``, ``too_long``,
        ``keyword`` o ``simple``)
    :rtype: tuple
    """
    if not config.routing:
        return config.model_large, "routing_disabled"
    if len(question) > config.router_max_chars:
        return config.model_large, "too_long"
    lowered = question.lower()
    if any(word in lowered for word in KEYWORDS):
        return config.model_large, "keyword"
    return config.model_small, "simple"
