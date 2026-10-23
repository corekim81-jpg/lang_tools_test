import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langfuse import Langfuse
from langsmith import Client, trace, tracing_context
from openai import OpenAI
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lab import chat_demo, common
from lab.__main__ import main


def test_interactive_history_and_reset(monkeypatch, tmp_path):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chat-test",
                "object": "chat.completion",
                "created": 0,
                "model": "test",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "general answer"},
                    }
                ],
            },
        )

    monkeypatch.setenv("LLM_MODEL", "test")
    monkeypatch.setenv("LLM_BASE_URL", "http://test.local/v1")
    monkeypatch.setattr(common, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(
        chat_demo,
        "model_client",
        lambda: OpenAI(
            api_key="synthetic",
            base_url="http://test.local/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )
    questions = iter(["", "이름은 바다야", "내 이름은?", "/reset", "안녕", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(questions))
    chat_demo.run(SimpleNamespace(question=None, trace="none", stream=False))
    assert len(requests) == 3
    first, second, third = [r["messages"] for r in requests]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert second[1]["content"] == "이름은 바다야"
    assert second[2]["content"] == "general answer"
    assert len(first) == len(third) == 2
    assert "근거 문서" not in json.dumps(requests, ensure_ascii=False)
    files = list(tmp_path.glob("chat-*.json"))
    assert len(files) == 2
    assert sorted(len(json.loads(p.read_text(encoding="utf-8"))["turns"]) for p in files) == [1, 2]


def test_general_history_is_bounded_without_splitting_turns():
    history = [
        item
        for n in range(25)
        for item in ({"role": "user", "content": str(n)}, {"role": "assistant", "content": f"a{n}"})
    ]
    messages = chat_demo.general_messages(history, "next")
    assert len(messages) == 42
    assert messages[1] == {"role": "user", "content": "5"}
    assert messages[-2] == {"role": "assistant", "content": "a24"}


def test_chat_requires_live_and_selected_credentials(monkeypatch):
    monkeypatch.setattr("lab.__main__.load_env", lambda: None)
    with pytest.raises(SystemExit) as error:
        main(["chat", "--question", "hello"])
    assert error.value.code == 2
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LANGSMITH_API_KEY"):
        with chat_demo.observers("both"):
            pytest.fail("Missing credentials must fail before any inference")


def test_both_sdk_observers_capture_session_usage_and_mask(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    exporter = InMemorySpanExporter()
    ls = Client(api_url="http://127.0.0.1:9", api_key="synthetic", auto_batch_tracing=False)
    lf = Langfuse(
        public_key=f"pk-lf-chat-{uuid4()}",
        secret_key="synthetic",
        span_exporter=exporter,
        mask=common.scrub,
    )
    report = {}
    try:
        with tracing_context(enabled="local", client=ls), trace("root") as root:
            with chat_demo.record_turn(
                [{"role": "user", "content": "demo@example.com"}], "chat-session", report, ls, lf
            ):
                report.update(
                    answer="answer",
                    finish_reason="stop",
                    usage={"prompt_tokens": 20, "completion_tokens": 7, "total_tokens": 27},
                )
        ls_run = root.child_runs[0]
        assert ls_run.outputs["usage_metadata"]["total_tokens"] == 27
        assert ls_run.extra["metadata"]["session_id"] == "chat-session"
        assert set(report["trace_ids"]) == {"langsmith", "langfuse"}
        lf.flush()
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs["session.id"] == "chat-session"
        assert "27" in str(attrs)
        assert "[EMAIL]" in str(attrs) and "demo@example.com" not in str(attrs)
    finally:
        lf.shutdown()
