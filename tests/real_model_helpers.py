"""Modelos de prueba que se portan como uno real (sesion 6).

Un modelo real no siempre devuelve JSON limpio: lo envuelve en un bloque de
codigo, escribe texto antes o inventa una respuesta despues de pedir la
herramienta. Estos modelos reproducen esas conductas sin llamar a la red.
"""

import json

from app.llm import TOOL_RESULT_PREFIX

STYLES = ("fenced", "prefixed", "invented", "plain")
INVENTED_TEXT = "Pedro Inventado, gerente en Marte"
PLAIN_REPLY = "Claro, con gusto te ayudo con eso."


def _tool_call(employee_id):
    return json.dumps(
        {"tool": "get_employee", "args": {"employee_id": employee_id}}
    )


class RealisticModel:
    """Modelo de prueba que pide ``get_employee`` y responde con el resultado.

    :param style: ``fenced``, ``prefixed``, ``invented`` o ``plain``
    :type style: str
    :param employee_id: Empleado que pide al directorio
    :type employee_id: str
    """

    def __init__(self, style, employee_id="EMP-0004"):
        assert style in STYLES
        self.style = style
        self.employee_id = employee_id
        self.calls = []

    def complete(self, messages):
        """Devuelve la respuesta segun el estilo y el ultimo mensaje."""
        self.calls.append(list(messages))
        if self.style == "plain":
            return PLAIN_REPLY
        last = messages[-1]["content"]
        if last.startswith(TOOL_RESULT_PREFIX):
            data = last[len(TOOL_RESULT_PREFIX):]
            body = json.dumps({"answer": f"Según el directorio: {data}"})
            return self._wrap(body)
        call = _tool_call(self.employee_id)
        if self.style == "invented":
            fake = json.dumps({"answer": f"Es {INVENTED_TEXT}."})
            return f"{call}\n{fake}"
        return self._wrap(call)

    def _wrap(self, body):
        if self.style == "fenced":
            return f"```json\n{body}\n```"
        if self.style == "prefixed":
            return f"Voy a consultar el directorio.\n{body}"
        return body
