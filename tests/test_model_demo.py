from types import SimpleNamespace

import httpx
import pytest
from dotenv import dotenv_values
from openai import OpenAI

from lab import common, model_demo


@pytest.mark.parametrize("value", ["0", "-1", "bad"])
def test_invalid_token_budget_is_rejected(monkeypatch, value):
    monkeypatch.setenv("LLM_MAX_TOKENS", value)
    with pytest.raises(ValueError, match="LLM_MAX_TOKENS"):
        common.model_max_tokens()


def test_generation_uses_budget_and_rejects_truncation(monkeypatch):
    import json

    monkeypatch.setenv("LLM_MODEL", "reasoning-model")
    monkeypatch.setenv("LLM_MAX_TOKENS", "2048")

    def handler(request):
        assert json.loads(request.content)["max_tokens"] == 2048
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "reasoning-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "length",
                        "message": {"role": "assistant", "content": "partial"},
                    }
                ],
            },
        )

    client = OpenAI(
        api_key="synthetic",
        base_url="http://model.test/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(common, "model_client", lambda tool=None: client)
    with pytest.raises(ValueError, match="토큰 한도"):
        common.generate("CPU", [], mode="api")


def client_for(status, body):
    def handler(request):
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)

    return OpenAI(
        api_key="synthetic",
        base_url="http://model.test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_discover_saves_server_model_id_only(monkeypatch, tmp_path):
    monkeypatch.setattr(model_demo, "ROOT", tmp_path)
    env = tmp_path / ".env"
    env.write_text("LANGFUSE_SECRET_KEY=keep-this\n", encoding="utf-8")
    with client_for(
        200,
        {
            "object": "list",
            "data": [
                {"id": "qwen-server-model", "object": "model", "created": 0, "owned_by": "server"}
            ],
        },
    ) as client:
        assert model_demo.discover(client, save_model=True) == ["qwen-server-model"]
    values = dotenv_values(env)
    assert values["LLM_MODEL"] == "qwen-server-model"
    assert values["LANGFUSE_SECRET_KEY"] == "keep-this"


def test_discover_does_not_guess_when_multiple_models(monkeypatch, tmp_path):
    monkeypatch.setattr(model_demo, "ROOT", tmp_path)
    data = [
        {"id": name, "object": "model", "created": 0, "owned_by": "server"}
        for name in ["qwen-a", "qwen-b"]
    ]
    with client_for(200, {"object": "list", "data": data}) as client:
        with pytest.raises(ValueError, match="여러 개"):
            model_demo.discover(client, save_model=True)
    assert not (tmp_path / ".env").exists()


def test_proxy_cookie_error_is_actionable_and_does_not_dump_body(monkeypatch):
    monkeypatch.setattr(
        model_demo,
        "model_client",
        lambda: client_for(401, "Not Authenticated - INVALIDCOOKIE private-server-detail"),
    )
    with pytest.raises(ValueError, match="SSH 터널") as error:
        model_demo.run(SimpleNamespace(step="models", save_model=False))
    assert "private-server-detail" not in str(error.value)


def test_real_chat_report(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "ARTIFACTS", tmp_path)
    monkeypatch.setenv("LLM_MODEL", "qwen-server-model")
    monkeypatch.setenv("LLM_BASE_URL", "http://model.test/v1")
    body = {
        "id": "test",
        "object": "chat.completion",
        "created": 0,
        "model": "qwen-server-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "원인: CPU 사용률 상승"},
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    }
    with client_for(200, body) as client:
        report = model_demo.chat(client, "CPU 사용률이 높아요")
    assert report["mode"] == "api"
    assert report["usage"]["total_tokens"] == 30
    assert (tmp_path / "model-report.json").exists()


def test_empty_completion_is_not_reported_as_success(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "qwen-server-model")
    body = {
        "id": "test",
        "object": "chat.completion",
        "created": 0,
        "model": "qwen-server-model",
        "choices": [
            {"index": 0, "finish_reason": "length", "message": {"role": "assistant", "content": ""}}
        ],
    }
    with client_for(200, body) as client:
        with pytest.raises(ValueError, match="빈 답변"):
            model_demo.chat(client, "CPU")
