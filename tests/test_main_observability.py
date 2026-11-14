"""Pruebas del middleware y de las rutas de observabilidad de la API."""

import uuid

import pytest


@pytest.mark.parametrize("bad_id", ["", "x" * 129])
def test_unacceptable_request_id_is_replaced_by_a_uuid(client, bad_id):
    response = client.get("/health", headers={"X-Request-ID": bad_id})
    assert uuid.UUID(response.headers["X-Request-ID"])


def test_not_found_route_also_carries_a_request_id(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert uuid.UUID(response.headers["X-Request-ID"])


def test_invalid_question_counts_as_a_request_but_not_as_an_error(client):
    response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422
    assert response.headers["X-Request-ID"]
    metrics = client.get("/metrics").json()
    assert metrics["requests"] >= 1
    assert metrics["error_rate"] == 0
