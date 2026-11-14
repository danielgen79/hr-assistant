"""Pruebas del modelo real: Cloudflare AI Gateway con transporte simulado."""

import json

import httpx
import pytest

from app.llm import GatewayModel, ModelUnavailable

URL = (
    "https://gateway.ai.cloudflare.com/v1/acc/gw/"
    "workers-ai/v1/chat/completions"
)
MESSAGES = [{"role": "user", "content": "Hello"}]
GOOD_BODY = {
    "choices": [{"message": {"content": '{"answer": "Hi"}'}}],
    "usage": {"prompt_tokens": 11, "completion_tokens": 7},
}


def _model(handler, cache_ttl=0):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GatewayModel(
        account_id="acc",
        gateway_id="gw",
        api_token="tok-123",
        max_tokens=300,
        temperature=0,
        cache_ttl=cache_ttl,
        client=client,
    )


def test_request_follows_the_gateway_contract():
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(200, json=GOOD_BODY)

    _model(handler).complete_with_usage(MESSAGES, "some-model")
    request = seen["request"]
    assert str(request.url) == URL
    assert request.headers["Authorization"] == "Bearer tok-123"
    assert json.loads(request.content) == {
        "model": "some-model",
        "messages": MESSAGES,
        "max_tokens": 300,
        "temperature": 0,
    }


def test_text_and_tokens_come_from_the_response():
    model = _model(lambda request: httpx.Response(200, json=GOOD_BODY))
    result = model.complete_with_usage(MESSAGES, "some-model")
    assert result.text == '{"answer": "Hi"}'
    assert (result.input_tokens, result.output_tokens) == (11, 7)
    assert result.cached is False


def test_cache_header_is_sent_only_when_enabled_and_only_a_hit_counts():
    seen = []
    status = {"value": "HIT"}

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200, json=GOOD_BODY, headers={"cf-aig-cache-status": status["value"]}
        )

    off = _model(handler, cache_ttl=0).complete_with_usage(MESSAGES, "m")
    on = _model(handler, cache_ttl=3600).complete_with_usage(MESSAGES, "m")
    status["value"] = "MISS"
    miss = _model(handler, cache_ttl=3600).complete_with_usage(MESSAGES, "m")
    assert "cf-aig-cache-ttl" not in seen[0].headers
    assert seen[1].headers["cf-aig-cache-ttl"] == "3600"
    assert (off.cached, on.cached, miss.cached) == (True, True, False)


@pytest.mark.parametrize("failure", ["status", "network", "malformed"])
def test_any_gateway_failure_becomes_model_unavailable(failure):
    def handler(request):
        if failure == "network":
            raise httpx.ConnectError("boom", request=request)
        if failure == "status":
            return httpx.Response(500, json={"error": "down"})
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(ModelUnavailable) as caught:
        _model(handler).complete_with_usage(MESSAGES, "m")
    assert "tok-123" not in str(caught.value)
