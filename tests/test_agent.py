"""Pruebas del bucle del agente con un modelo falso guionizado."""

from helpers import ScriptedModel, answer_reply, tool_reply

LIMIT_MESSAGE = (
    "No pude completar la respuesta. Intenta con una pregunta más concreta."
)


_tool = tool_reply
_answer = answer_reply


def test_direct_answer_takes_one_step(make_agent):
    result = make_agent(ScriptedModel([_answer("Hola")])).run("Hi")
    assert result["answer"] == "Hola"
    assert result["steps"] == 1
    assert result["tools_used"] == []
    assert result["input_tokens"] > 0
    assert result["output_tokens"] > 0


def test_tool_result_is_fed_back_to_the_model(make_agent):
    model = ScriptedModel(
        [_tool("get_employee", employee_id="EMP-0004"), _answer("Es Jorge")]
    )
    result = make_agent(model).run("Who is EMP-0004?")
    assert result["tools_used"] == ["get_employee"]
    assert result["steps"] == 2
    last = model.calls[1][-1]
    assert last["role"] == "user"
    assert last["content"].startswith("Resultado de la herramienta: ")
    assert "Jorge Díaz" in last["content"]


def test_step_limit_returns_the_fixed_message(make_agent):
    model = ScriptedModel([_tool("get_employee", employee_id="EMP-0004")])
    result = make_agent(model, max_steps=1).run("Who is EMP-0004?")
    assert result["answer"] == LIMIT_MESSAGE
    assert result["steps"] == 1


def test_invalid_model_output_is_handled_without_raising(make_agent):
    model = ScriptedModel(["this is not json", _answer("Recuperado")])
    result = make_agent(model).run("Hi")
    assert isinstance(result["answer"], str)
    assert result["steps"] >= 1

    never_valid = ScriptedModel(["nope"] * 5)
    limited = make_agent(never_valid, max_steps=2).run("Hi")
    assert limited["answer"] == LIMIT_MESSAGE
    assert limited["steps"] == 2


def test_unknown_tool_is_a_controlled_error(make_agent):
    model = ScriptedModel([_tool("delete_employee", employee_id="EMP-0001")])
    result = make_agent(model, max_steps=1).run("Remove EMP-0001")
    assert result["answer"] == LIMIT_MESSAGE
    assert "delete_employee" not in result["tools_used"]


def test_history_is_included_in_the_messages(make_agent):
    model = ScriptedModel([_answer("Ok")])
    history = [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
    ]
    make_agent(model).run("second question", history)
    contents = [message["content"] for message in model.calls[0]]
    assert contents[-3:] == ["first question", "first answer", "second question"]
