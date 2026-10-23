"""Exercise installed SDKs without a cloud account or a real model endpoint."""

import json
from uuid import uuid4

import httpx
import pytest
from langfuse import Langfuse
from langsmith import Client, trace, tracing_context
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lab import common


def test_langsmith_real_sdk_parent_child_traces():
    from lab.langsmith_demo import pipeline

    client = Client(api_url="http://127.0.0.1:9", api_key="synthetic", auto_batch_tracing=False)
    with tracing_context(enabled="local", client=client):
        with trace("local-test") as root:
            result = pipeline(common.cases()[0]["inputs"])
    assert "KB-CPU" in result["answer"]
    assert len(root.child_runs) == 1
    application = root.child_runs[0]
    assert application.parent_run_id == root.id
    assert {child.name for child in application.child_runs} == {
        "knowledge-search",
        "mock-generation",
    }


def test_langfuse_real_sdk_exports_nested_observations():
    from lab.langfuse_demo import pipeline

    exporter = InMemorySpanExporter()
    client = Langfuse(
        public_key=f"pk-lf-test-{uuid4()}",
        secret_key="synthetic",
        base_url="http://127.0.0.1:9",
        span_exporter=exporter,
        mask=common.scrub,
    )
    try:
        result, trace_id = pipeline(client, common.cases()[0]["inputs"])
        with client.start_as_current_observation(
            name="masked-input", input={"email": "demo@example.com", "api_key": "never-export"}
        ):
            pass
        client.flush()
        spans = exporter.get_finished_spans()
        assert "KB-CPU" in result["answer"]
        assert len(trace_id) == 32
        assert {span.name for span in spans} == {
            "incident-agent",
            "knowledge-search",
            "mock-generation",
            "masked-input",
        }
        root = next(span for span in spans if span.name == "incident-agent")
        assert all(
            span.parent.span_id == root.context.span_id
            for span in spans
            if span.name in {"knowledge-search", "mock-generation"}
        )
        masked = next(span for span in spans if span.name == "masked-input")
        attrs = str(masked.attributes)
        assert "[EMAIL]" in attrs and "[REDACTED]" in attrs
        assert "never-export" not in attrs and "demo@example.com" not in attrs
    finally:
        client.shutdown()


def test_api_adapter_uses_endpoint_response_not_fixture(monkeypatch):
    from openai import OpenAI

    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chat-test",
                "object": "chat.completion",
                "created": 0,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "server answer"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
            },
        )

    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setattr(
        common,
        "model_client",
        lambda tool=None: OpenAI(
            api_key="synthetic",
            base_url="http://test.local/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )
    assert common.answer({"question": "CPU"}, mode="api")["answer"] == "server answer"
    assert seen[0]["model"] == "test-model"
    assert "KB-CPU" in seen[0]["messages"][1]["content"]


def test_judge_rejects_non_json(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import pytest

    mock = MagicMock()
    mock.__enter__.return_value = mock
    mock.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not JSON"), finish_reason="stop")]
    )
    monkeypatch.setattr(common, "model_client", lambda: mock)
    monkeypatch.setenv("LLM_MODEL", "test-model")
    with pytest.raises(ValueError):
        common.judge("question", "answer", {"keywords": ["CPU"]})


@pytest.mark.parametrize("tool", ["langsmith", "langfuse"])
def test_real_model_wrappers_stream_and_capture_usage(tool, monkeypatch):
    """Use actual model wrappers with a fake HTTP transport, including usage-only final chunk."""
    from contextlib import nullcontext

    from openai import OpenAI

    chunks = [
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "CPU"},
                    "finish_reason": None,
                }
            ]
        },
        {"choices": [{"index": 0, "delta": {"content": " answer"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}},
    ]
    stream = (
        "".join(
            "data: "
            + json.dumps(
                {
                    "id": "chat-stream",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "test-model",
                    **chunk,
                }
            )
            + "\n\n"
            for chunk in chunks
        )
        + "data: [DONE]\n\n"
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=stream.encode(), headers={"content-type": "text/event-stream"}
        )
    )
    exporter = InMemorySpanExporter()
    lf = None
    cls = OpenAI
    if tool == "langfuse":
        from langfuse.openai import OpenAI as TracedOpenAI

        public = f"pk-lf-stream-{uuid4()}"
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", public)
        lf = Langfuse(public_key=public, secret_key="synthetic", span_exporter=exporter)
        cls = TracedOpenAI
        outer = nullcontext()
        root_context = lf.start_as_current_observation(name="wrapper-root")
    else:
        client = Client(api_url="http://127.0.0.1:9", api_key="synthetic", auto_batch_tracing=False)
        outer = tracing_context(enabled="local", client=client)
        root_context = trace("wrapper-root")
    llm = cls(
        api_key="synthetic",
        base_url="http://test.local/v1",
        http_client=httpx.Client(transport=transport),
    )
    if tool == "langsmith":
        from langsmith.wrappers import wrap_openai

        llm = wrap_openai(llm)
    try:
        with outer, root_context as root, llm:
            with llm.chat.completions.create(
                model="test-model",
                messages=[{"role": "user", "content": "CPU"}],
                stream=True,
                stream_options={"include_usage": True},
                **({"langfuse_public_key": public} if lf else {}),
            ) as response:
                output = "".join(
                    chunk.choices[0].delta.content or "" for chunk in response if chunk.choices
                )
        assert output == "CPU answer"
        if lf:
            lf.flush()
            assert len(exporter.get_finished_spans()) >= 2
            assert any("usage" in str(span.attributes) for span in exporter.get_finished_spans())
        else:
            assert root.child_runs
            assert root.child_runs[0].outputs["usage_metadata"]["total_tokens"] == 12
    finally:
        if lf:
            lf.shutdown()
