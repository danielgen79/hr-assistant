"""Agente con bucle acotado que usa herramientas de solo lectura."""

import json
from dataclasses import dataclass

from app.llm import TOOL_RESULT_PREFIX, Completion, count_tokens
from app.pricing import compute_cost
from app.tracing import traced

LIMIT_MESSAGE = (
    "No pude completar la respuesta. Intenta con una pregunta más concreta."
)
KNOWN_TOOLS = ("get_employee", "search_by_department")


def _discard(_event, **_fields):
    """Descarta el evento (registro apagado)."""


@dataclass
class _Usage:
    """Uso acumulado de una corrida: tokens, llamadas cacheadas y costo."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_calls: int = 0
    cost_usd: float = 0.0


class Agent:
    """Agente que alterna entre el modelo y las herramientas.

    :param model: Objeto con ``complete(messages)``
    :param directory: Directorio de empleados
    :type directory: Directory
    :param max_steps: Tope de llamadas al modelo
    :type max_steps: int
    :param log: Funcion ``log(event, **fields)`` para los eventos (opcional)
    :type log: Callable or None
    :param prices: Precios por modelo; sin ellos el costo es 0 (opcional)
    :type prices: dict or None
    :param history_window: Ultimos mensajes de historial que se mandan
        (``None``: todos)
    :type history_window: int or None
    """

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(
        self, model, directory, max_steps, log=None, prices=None,
        history_window=None,
    ):
        self._model = model
        self._directory = directory
        self._max_steps = max_steps
        self._log = log or _discard
        self._prices = prices
        self._history_window = history_window

    def _window(self, history):
        """Deja solo los ultimos mensajes del historial segun la ventana."""
        if self._history_window is None:
            return history
        if self._history_window == 0:
            return []
        return history[-self._history_window:]

    @traced("agent_run", "chain")
    def run(self, question, history=None, model_name=None):
        """Responde una pregunta.

        :param question: Pregunta del usuario
        :type question: str
        :param history: Mensajes previos enviados por el cliente
        :type history: list or None
        :param model_name: Modelo elegido por el enrutador (para el precio)
        :type model_name: str or None
        :return: ``answer``, ``steps``, ``tools_used``, tokens, ``cached_calls``
            y ``cost_usd``
        :rtype: dict
        """
        messages = self._build_messages(question, history)
        usage = _Usage()
        tools_used = []
        answer = None
        steps = 0
        while answer is None and steps < self._max_steps:
            steps += 1
            completion = self._complete(messages, model_name)
            self._add_usage(usage, completion, model_name)
            payload = self._parse(completion.text)
            if payload is not None and isinstance(payload.get("answer"), str):
                answer = payload["answer"]
                break
            feedback = self._run_tool(payload, tools_used)
            messages.append({"role": "assistant", "content": completion.text})
            messages.append(
                {"role": "user", "content": TOOL_RESULT_PREFIX + feedback}
            )
        self._log_run(question, history, steps, tools_used, usage, answer is None)
        return {
            "answer": LIMIT_MESSAGE if answer is None else answer,
            "steps": steps,
            "tools_used": tools_used,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cached_calls": usage.cached_calls,
            "cost_usd": usage.cost_usd,
        }

    def _build_messages(self, question, history):
        """Arma la conversacion: ventana de historial mas la pregunta."""
        sent = self._window(list(history or []))
        messages = [dict(item) for item in sent]
        messages.append({"role": "user", "content": question})
        return messages

    def _add_usage(self, usage, completion, model_name):
        """Suma tokens, llamadas cacheadas y costo de una respuesta."""
        usage.input_tokens += completion.input_tokens
        usage.output_tokens += completion.output_tokens
        if completion.cached:
            usage.cached_calls += 1
        elif self._prices is not None and model_name is not None:
            usage.cost_usd += compute_cost(
                self._prices, model_name,
                completion.input_tokens, completion.output_tokens,
            )

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def _log_run(self, question, history, steps, tools_used, usage, stopped):
        """Registra la corrida; nunca incluye el texto de pregunta ni respuesta."""
        self._log(
            "agent_run",
            question_chars=len(question),
            history_messages=len(history or []),
            steps=steps,
            tools=tools_used,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            stopped=stopped,
        )

    @traced("model", "llm")
    def _complete(self, messages, model_name):
        """Llama al modelo.

        Si el modelo solo tiene ``complete``, los tokens se cuentan de forma
        aproximada y la llamada nunca es cacheada.

        :param messages: Conversacion como lista de mensajes
        :type messages: list
        :param model_name: Modelo que debe responder
        :type model_name: str or None
        :return: La respuesta del modelo con su uso
        :rtype: Completion
        """
        with_usage = getattr(self._model, "complete_with_usage", None)
        if with_usage is not None:
            return with_usage(messages, model_name)
        text = self._model.complete(messages)
        return Completion(
            text, count_tokens([m["content"] for m in messages]),
            count_tokens([text]), False,
        )

    @staticmethod
    def _parse(reply):
        """Interpreta la respuesta del modelo.

        :return: El objeto JSON o ``None`` si no es un objeto valido
        :rtype: dict or None
        """
        try:
            payload = json.loads(reply)
        except (TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    @traced("tool", "tool")
    def _run_tool(self, payload, tools_used):
        """Ejecuta la herramienta pedida y devuelve el texto del resultado.

        Los errores se devuelven como texto para que el modelo los vea.
        """
        if payload is None:
            return "error: la respuesta del modelo no es un JSON valido."
        name = payload.get("tool")
        args = payload.get("args")
        if not isinstance(args, dict):
            args = {}
        if name in KNOWN_TOOLS:
            self._log("audit", action="tool_call", tool=name, args=args)
        try:
            if name == "get_employee":
                found = self._directory.get_employee(args["employee_id"])
                if found is None:
                    employee_id = args["employee_id"]
                    result = f"El empleado {employee_id} no existe."
                else:
                    result = json.dumps(found, ensure_ascii=False)
            elif name == "search_by_department":
                found = self._directory.search_by_department(args["department"])
                result = json.dumps(found, ensure_ascii=False)
            else:
                return f"error: herramienta desconocida {name!r}."
        except KeyError as error:
            return f"error: falta el argumento {error}."
        tools_used.append(name)
        return result
