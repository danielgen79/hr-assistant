"""Pruebas de seguridad de la pagina web."""

from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "app" / "static" / "index.html"


def test_page_paints_text_with_text_content_never_inner_html():
    html = INDEX.read_text(encoding="utf-8")
    assert "innerHTML" not in html
    assert "textContent" in html


def test_page_sends_the_key_in_a_header_and_never_writes_one_in_its_code():
    html = INDEX.read_text(encoding="utf-8")
    assert 'data-testid="api-key"' in html
    assert 'type="password"' in html
    assert "sessionStorage" in html
    assert "localStorage" not in html
    assert "X-API-Key" in html
    assert "Retry-After" in html
    assert "Clave inválida" in html
    assert "Demasiadas preguntas; espera" in html
    assert "demo-example-key" not in html
