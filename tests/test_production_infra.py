"""Pruebas del pipeline de CI, del Blueprint de Render y de las pruebas e2e."""

import re
from pathlib import Path

PRODUCT_DIR = Path(__file__).resolve().parents[1]


def _read(*parts):
    return PRODUCT_DIR.joinpath(*parts).read_text(encoding="utf-8")


def _job_block(workflow, job):
    """Texto de un trabajo del workflow, hasta el siguiente trabajo."""
    match = re.search(
        rf"^  {job}:\n(.*?)(?=^  \w+:\n|\Z)", workflow, re.MULTILINE | re.DOTALL
    )
    assert match, job
    return match.group(1)


def test_ci_stages_are_chained_in_order():
    workflow = _read(".github", "workflows", "ci.yml")
    assert "needs:" not in _job_block(workflow, "style")
    for job, previous in (("unit", "style"), ("e2e", "unit"), ("docker", "e2e")):
        assert re.search(
            rf"^    needs:\s*\[?{previous}\]?\s*$",
            _job_block(workflow, job),
            re.MULTILINE,
        ), job


def test_ci_style_uses_88_columns_and_docker_job_builds_the_image():
    workflow = _read(".github", "workflows", "ci.yml")
    assert "pylint" in _job_block(workflow, "style")
    assert "--max-line-length=88" in _job_block(workflow, "style")
    assert "docker build" in _job_block(workflow, "docker")
    assert "playwright" in _job_block(workflow, "e2e")


def test_render_blueprint_has_one_web_service_with_a_valid_name():
    render = _read("render.yaml")
    assert len(re.findall(r"^\s*-\s*type:", render, re.MULTILINE)) == 1
    assert re.search(r"type:\s*web", render)
    name = re.search(r"^\s+name:\s*(\S+)", render, re.MULTILINE).group(1)
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", name), name


def test_e2e_tests_read_the_key_from_the_environment_and_never_write_it():
    source = _read("e2e", "test_ask_flow.py")
    assert 'os.environ["E2E_API_KEY"]' in source
    assert "demo-example-key" not in source
