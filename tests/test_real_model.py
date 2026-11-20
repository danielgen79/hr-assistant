"""Pruebas de la sesion 6: mensaje de sistema y lector de JSON tolerante."""

import json
import re
import time
from pathlib import Path

import pytest
from helpers import ScriptedModel, UsageModel, answer_reply, tool_reply
from real_model_helpers import INVENTED_TEXT, RealisticModel

from app import tracing
from app.agent import SYSTEM_MESSAGE, Agent
from app.llm import TOOL_RESULT_PREFIX, FakeModel, count_tokens

PRODUCT_DIR = Path(__file__).resolve().parents[1]
GATEWAY_VARIABLES = ("CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN")
PARSE_ERROR = "error: la respuesta del modelo no es un JSON valido."
HISTORY = [
    {"role": "user", "content": "first question"},
    {"role": "assistant", "content": "first answer"},
    {"role": "user", "content": "second question"},
    {"role": "assistant", "content": "second answer"},
]


# --- Mensaje de sistema ---------------------------------------------------


def test_system_message_is_the_first_message_the_model_receives(make_agent):
    model = ScriptedModel([answer_reply("Ok")])
    make_agent(model).run("Hi")
    messages = model.calls[0]
    assert messages[0] == {"role": "system", "content": SYSTEM_MESSAGE}
    assert messages[-1] == {"role": "user", "content": "Hi"}
    assert [m["role"] for m in messages].count("system") == 1


def test_system_message_names_both_tools_and_the_protocol():
    for expected in (
        "get_employee", "employee_id", "search_by_department", "department",
        "JSON", '{"answer"', "Resultado de la herramienta:",
    ):
        assert expected in SYSTEM_MESSAGE, expected
    assert TOOL_RESULT_PREFIX.strip() in SYSTEM_MESSAGE


def test_system_message_has_no_directory_data_or_keys():
    path = PRODUCT_DIR / "data" / "employees.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for employee in data:
        assert employee["name"] not in SYSTEM_MESSAGE
    lowered = SYSTEM_MESSAGE.lower()
    for secret in ("api_key", "token", "password", "secret"):
        assert secret not in lowered, secret


@pytest.mark.parametrize("window", [0, 1, 10])
def test_history_window_neither_trims_nor_counts_the_system_message(
    directory, window
):
    model = ScriptedModel([answer_reply("Ok")])
    Agent(model, directory, 3, history_window=window).run("Hi", HISTORY)
    messages = model.calls[0]
    kept = min(window, len(HISTORY))
    assert messages[0]["role"] == "system"
    assert len(messages) == 1 + kept + 1


def test_system_message_does_not_use_up_the_history_limit(build_client):
    model = ScriptedModel([answer_reply("Ok")])
    client = build_client({"MAX_HISTORY_MESSAGES": "2"}, model=model)
    history = HISTORY[:2]
    assert client.post(
        "/ask", json={"question": "Hi", "history": history}
    ).status_code == 200
    assert model.calls[0][0]["role"] == "system"
    too_long = client.post("/ask", json={"question": "Hi", "history": HISTORY[:3]})
    assert too_long.status_code == 422


# --- Lector tolerante -----------------------------------------------------


TOOL = {"tool": "get_employee", "args": {"employee_id": "EMP-0004"}}
TOOL_TEXT = json.dumps(TOOL)
ANSWER_TEXT = json.dumps({"answer": "Hola"})


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (TOOL_TEXT, TOOL),
        (f"Voy a consultar.\n{TOOL_TEXT}", TOOL),
        (f"```json\n{TOOL_TEXT}\n```", TOOL),
        (f"{TOOL_TEXT}\n{ANSWER_TEXT}", TOOL),
        (f"{ANSWER_TEXT} {TOOL_TEXT}", {"answer": "Hola"}),
        ('{"answer": "usa } y { bien"}', {"answer": "usa } y { bien"}),
        ('x {"tool": "t", "args": {"a": {"b": 1}}} y',
         {"tool": "t", "args": {"a": {"b": 1}}}),
    ],
    ids=["clean", "text-before", "code-block", "two-objects", "answer-first",
         "braces-in-string", "nested-object"],
)
def test_parse_takes_only_the_first_json_object(reply, expected):
    assert Agent._parse(reply) == expected  # pylint: disable=protected-access


@pytest.mark.parametrize(
    "reply",
    ["", "Claro, con gusto te ayudo.", '{"answer": "sin cierre"', "[1, 2]", "42"],
    ids=["empty", "plain-text", "unclosed", "list", "number"],
)
def test_text_without_a_json_object_is_still_invalid(reply):
    assert Agent._parse(reply) is None  # pylint: disable=protected-access


def test_parse_does_not_stall_on_huge_or_hostile_input():
    started = time.monotonic()
    for reply in ("{" * 100_000, "x" * 1_000_000, '{"a": "' + "}" * 100_000):
        assert Agent._parse(reply) is None  # pylint: disable=protected-access
    assert time.monotonic() - started < 2


# --- Conducta ante un modelo que se porta como uno real ---------------------


def test_invented_answer_after_the_tool_call_is_never_used(make_agent):
    model = RealisticModel("invented")
    result = make_agent(model).run("Who is EMP-0004?")
    assert result["tools_used"] == ["get_employee"]
    assert "Jorge Díaz" in result["answer"]
    assert INVENTED_TEXT not in result["answer"]
    fed_back = model.calls[1][-1]["content"]
    assert fed_back.startswith(TOOL_RESULT_PREFIX)
    assert INVENTED_TEXT not in fed_back


def test_assistant_message_kept_in_context_has_only_the_first_object(make_agent):
    model = RealisticModel("invented")
    make_agent(model).run("Who is EMP-0004?")
    next_step = model.calls[1]
    assistant = next_step[-2]
    assert assistant["role"] == "assistant"
    assert INVENTED_TEXT not in assistant["content"]
    assert "answer" not in assistant["content"]
    assert json.loads(assistant["content"]) == {
        "tool": "get_employee", "args": {"employee_id": "EMP-0004"},
    }


def test_plain_text_gets_the_same_error_and_ends_at_the_step_limit(make_agent):
    model = RealisticModel("plain")
    result = make_agent(model, max_steps=2).run("Who is EMP-0004?")
    assert result["steps"] == 2
    assert result["tools_used"] == []
    assert result["answer"].startswith("No pude completar la respuesta")
    assert model.calls[1][-1]["content"] == TOOL_RESULT_PREFIX + PARSE_ERROR


# --- Uso de tokens ----------------------------------------------------------


def test_input_tokens_include_the_system_message(make_agent):
    plain = make_agent(ScriptedModel([answer_reply("Ok")])).run("Hi there")
    assert plain["input_tokens"] == count_tokens([SYSTEM_MESSAGE, "Hi there"])

    usage_model = UsageModel([answer_reply("Ok")], input_tokens=100)
    result = make_agent(usage_model).run("Hi there")
    assert usage_model.calls[0][0]["role"] == "system"
    assert result["input_tokens"] == 100


# --- Privacidad -------------------------------------------------------------


def test_system_message_is_not_written_to_the_log(directory):
    events = []

    def log(event, **fields):
        events.append((event, fields))

    model = ScriptedModel([tool_reply("get_employee", employee_id="EMP-0004"),
                           answer_reply("Ok")])
    Agent(model, directory, 3, log=log).run("Who is EMP-0004?")
    names = [name for name, _fields in events]
    assert "agent_run" in names and "audit" in names
    dumped = json.dumps(events, ensure_ascii=False)
    assert SYSTEM_MESSAGE[:40] not in dumped
    assert "get_employee" in dumped


def test_system_message_is_not_in_the_traced_model_arguments(
    monkeypatch, directory
):
    recorded = []

    def traceable(name, run_type, client):  # pylint: disable=unused-argument
        def decorate(func):
            def wrapped(*args, langsmith_extra=None, **kwargs):
                recorded.append((name, args, kwargs, langsmith_extra))
                return func(*args, **kwargs)

            return wrapped

        return decorate

    # pylint: disable=protected-access
    monkeypatch.setitem(tracing._STATE, "traceable", traceable)
    monkeypatch.setitem(tracing._STATE, "client", None)
    result = Agent(ScriptedModel([answer_reply("Ok")]), directory, 3).run("Hi")
    assert result["answer"] == "Ok"
    traced_names = {item[0] for item in recorded}
    assert "model" in traced_names
    for item in recorded:
        dumped = json.dumps(item[1:], default=str, ensure_ascii=False)
        assert SYSTEM_MESSAGE[:40] not in dumped
        assert '"role": "system"' not in dumped


# --- Modelo simulado y despliegue -------------------------------------------


def test_simulated_model_answers_the_same_with_a_system_message_in_front(
    directory,
):
    model = FakeModel(directory)
    system = {"role": "system", "content": SYSTEM_MESSAGE}
    questions = ["¿Quién es EMP-0004?", "Hola", "Empleados de Tecnología"]
    for question in questions:
        user = {"role": "user", "content": question}
        assert model.complete([system, user]) == model.complete([user])
    result = Agent(model, directory, 3).run("¿Quién es EMP-0004?")
    assert result["tools_used"] == ["get_employee"]
    assert "Jorge Díaz" in result["answer"]


def test_deployment_files_ask_for_the_three_gateway_variables():
    render = (PRODUCT_DIR / "render.yaml").read_text(encoding="utf-8")
    for name in GATEWAY_VARIABLES:
        assert re.search(rf"key:\s*{name}\s*\n\s*sync:\s*false", render), name
    readme = (PRODUCT_DIR / "README.md").read_text(encoding="utf-8")
    for name in GATEWAY_VARIABLES:
        assert name in readme, name
