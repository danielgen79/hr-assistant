"""End-to-end tests of the HR Assistant page (session 4, API key required)."""

import os
import re

from playwright.sync_api import Page, expect

FIRST_QUESTION = "How many vacation days do I have?"
SECOND_QUESTION = "And how many sick days?"
WRONG_KEY = "this-key-is-not-valid-0000"


def valid_key() -> str:
    """Read the key that the verification step puts in E2E_API_KEY."""
    return os.environ["E2E_API_KEY"]


def ask(page: Page, question: str, key: str | None = None) -> None:
    """Type the API key first, then the question, and send it with the button."""
    page.get_by_test_id("api-key").fill(valid_key() if key is None else key)
    page.get_by_test_id("question").fill(question)
    page.get_by_test_id("send").click()


def test_question_and_its_answer_with_request_id_show_up_after_sending(page: Page):
    page.goto("/")
    ask(page, FIRST_QUESTION)
    expect(page.get_by_test_id("answer")).to_contain_text(FIRST_QUESTION)
    expect(page.get_by_test_id("answer")).to_contain_text(
        re.compile(r"request_id:\s*\S+")
    )
    expect(page.get_by_test_id("answer")).not_to_contain_text("Clave inválida")


def test_wrong_api_key_shows_invalid_key_message_and_no_answer(page: Page):
    page.goto("/")
    ask(page, FIRST_QUESTION, key=WRONG_KEY)
    expect(page.get_by_test_id("answer")).to_contain_text("Clave inválida")
    expect(page.get_by_test_id("answer")).not_to_contain_text("Herramientas usadas")


def test_input_is_cleared_after_sending(page: Page):
    page.goto("/")
    ask(page, FIRST_QUESTION)
    expect(page.get_by_test_id("question")).to_have_value("")


def test_empty_question_shows_an_error_message_in_spanish(page: Page):
    page.goto("/")
    page.get_by_test_id("api-key").fill(valid_key())
    page.get_by_test_id("send").click()
    expect(page.get_by_test_id("answer")).to_contain_text(
        "Escribe una pregunta antes de enviar."
    )
    expect(page.get_by_test_id("answer")).not_to_contain_text("request_id:")


def test_second_question_keeps_the_previous_conversation_on_screen(page: Page):
    page.goto("/")
    ask(page, FIRST_QUESTION)
    expect(page.get_by_test_id("answer")).to_contain_text("request_id:")
    ask(page, SECOND_QUESTION)
    answer = page.get_by_test_id("answer")
    expect(answer).to_contain_text(SECOND_QUESTION)
    expect(answer).to_contain_text(FIRST_QUESTION)
    expect(answer).to_contain_text(re.compile(r"request_id:[\s\S]*request_id:"))


def test_conversation_is_still_on_screen_after_reloading_the_page(page: Page):
    page.goto("/")
    ask(page, FIRST_QUESTION)
    expect(page.get_by_test_id("answer")).to_contain_text("request_id:")
    page.reload()
    expect(page.get_by_test_id("answer")).to_contain_text(FIRST_QUESTION)
