"""Pruebas de los archivos de despliegue y de la documentacion de S4.

Se leen como texto (sin PyYAML). Formato esperado en ``render.yaml``: cada
secreto es ``- key: NOMBRE`` seguido de ``sync: false`` en la linea siguiente.
"""

import re
from pathlib import Path

PRODUCT_DIR = Path(__file__).resolve().parents[1]
SECRETS = ("API_KEYS", "CF_ACCOUNT_ID", "CF_API_TOKEN")


def _read(*parts):
    return PRODUCT_DIR.joinpath(*parts).read_text(encoding="utf-8")


def test_container_ci_and_render_files_follow_the_specification():
    dockerfile = _read("Dockerfile")
    assert "FROM python:3.12-slim" in dockerfile
    users = re.findall(r"^USER\s+(\S+)", dockerfile, re.MULTILINE)
    assert users and users[-1] not in ("root", "0")
    assert "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}" in dockerfile
    for name in (".dockerignore", ".gitignore"):
        entries = _read(name).splitlines()
        assert ".env" in entries
    ignored = _read(".dockerignore").splitlines()
    assert "tests/" in ignored and "e2e/" in ignored
    assert "__pycache__" in " ".join(ignored)
    workflow = _read(".github", "workflows", "ci.yml")
    assert "push" in workflow and "pull_request" in workflow
    for job in ("style:", "unit:", "e2e:", "docker:"):
        assert re.search(rf"^  {job}", workflow, re.MULTILINE), job
    assert workflow.count("needs:") >= 3
    assert re.search(r"fail[-_]under[= ]+80", workflow)
    render = _read("render.yaml")
    for expected in (
        "runtime: docker", "plan: free", "healthCheckPath: /health",
        "autoDeployTrigger: checksPass",
    ):
        assert expected in render
    assert re.search(r"key:\s*ENVIRONMENT\s*\n\s*value:\s*production", render)
    assert re.search(r"key:\s*MODEL_PROVIDER\s*\n\s*value:\s*gateway", render)
    for name in ("HIDE_INPUTS", "HIDE_OUTPUTS"):
        assert re.search(rf"key:\s*{name}\s*\n\s*value:\s*\"?true", render)
    for name in SECRETS:
        assert re.search(rf"key:\s*{name}\s*\n\s*sync:\s*false", render), name
    assert "LANGSMITH_API_KEY" not in render


def test_readme_and_checklist_explain_the_key_rules():
    readme = _read("README.md")
    assert "demo-example-key-0000" in readme
    assert "modo abierto" in readme.lower()
    assert "401" in readme
    assert "ENVIRONMENT=production" in readme
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in _read("doc", "compliance-checklist.md").splitlines()
        if line.startswith("|") and not re.match(r"^\|[\s:|-]+$", line)
    ]
    body = rows[1:]
    assert len(body) >= 5
    for row in body:
        assert len(row) == 3
        assert all(row), row
    assert any("demo-example-key-0000" in " ".join(row) for row in body)
