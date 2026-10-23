"""Langfuse Python SDK 5 examples; requires server >= 4.59.0."""

from __future__ import annotations

import asyncio
import os
from statistics import mean
from uuid import NAMESPACE_URL, uuid5

from langfuse import Langfuse, observe, propagate_attributes
from langfuse.experiment import Evaluation

from lab.common import (
    ROOT,
    SYSTEM,
    cases,
    generate,
    judge,
    messages,
    model_client,
    prefix,
    require_env,
    retrieve,
    save_json,
    score_answer,
    scrub,
    stamp,
    state,
)


def pipeline(client, inputs, mode="mock", variant="good"):
    with client.start_as_current_observation(
        name="incident-agent", as_type="agent", input=inputs
    ) as root:
        with client.start_as_current_observation(
            name="knowledge-search", as_type="retriever", input=inputs
        ) as search:
            docs = retrieve(inputs["question"])
            search.update(output=docs)
        with client.start_as_current_observation(
            name="mock-generation" if mode == "mock" else "model-generation",
            as_type="generation",
            input=messages(inputs["question"], docs),
            model="mock-fixture" if mode == "mock" else os.environ["LLM_MODEL"],
            metadata={"simulation": mode == "mock", "variant": variant},
        ) as generation:
            text = generate(inputs["question"], docs, mode=mode, variant=variant, tool="langfuse")
            generation.update(output=text)
        root.update(output={"answer": text})
        return {"answer": text}, root.trace_id


def tracing(client, mode):
    session = f"{prefix()}-{stamp()}"
    with propagate_attributes(
        user_id="demo-user",
        session_id=session,
        tags=["lab", mode],
        metadata={"lab_prefix": prefix()},
        trace_name="incident-session",
    ):
        output, trace_id = pipeline(client, cases()[0]["inputs"], mode)
        # Second turn shares a session, but has a distinct trace.
        pipeline(client, cases()[1]["inputs"], mode)
    try:
        with client.start_as_current_observation(
            name="intentional-error", input={"synthetic": True}
        ):
            raise RuntimeError("실습용 검색 타임아웃 (의도한 오류)")
    except RuntimeError:
        pass
    # Manual lifecycle and typed tool spans.
    manual = client.start_observation(name="manual-tool", as_type="tool")
    try:
        manual.update(
            input={"contact": "demo@example.com", "api_key": "synthetic"},
            output={"status": "example"},
        )
    finally:
        manual.end()
    client.flush()
    state("langfuse", trace_id=trace_id, session_id=session, output=output)
    print(f"Trace: {client.get_trace_url(trace_id=trace_id)}")
    return trace_id


def async_demo(client, mode):
    @observe(name="async-incident", as_type="chain")
    async def task(inputs):
        output, _ = await asyncio.to_thread(pipeline, client, inputs, mode)
        return output

    async def batch():
        return await asyncio.gather(*(task(c["inputs"]) for c in cases()[:2]))

    print(asyncio.run(batch()))


def prompts(client, mode):
    name = f"{prefix()}-incident"
    first = client.create_prompt(
        name=name, type="text", prompt="질문: {{question}}", labels=["lab-baseline"], tags=["lab"]
    )
    second = client.create_prompt(
        name=name,
        type="text",
        prompt=SYSTEM + "\n근거: {{context}}\n질문: {{question}}",
        labels=["lab-candidate"],
        config={"max_tokens": 256},
    )
    client.update_prompt(name=name, version=second.version, new_labels=["lab-tested"])
    prompt = client.get_prompt(name, label="lab-tested", cache_ttl_seconds=60)
    compiled = prompt.compile(context="CPU 사용률 점검", question="CPU가 높아요")
    with client.start_as_current_observation(
        name="prompt-linked-generation",
        as_type="generation",
        prompt=prompt,
        input=compiled,
        metadata={"simulation": True},
    ) as gen:
        gen.update(output="프롬프트 연결을 보여주는 합성 응답")
    chat = client.create_prompt(
        name=f"{name}-chat",
        type="chat",
        prompt=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "{{question}}"},
        ],
        labels=["lab-tested"],
    )
    print(chat.compile(question="OOMKilled 원인을 알려줘"))
    print(f"Text versions: {first.version} → {second.version}; cache=60s; label=lab-tested")
    state("langfuse", prompt=name)


def dataset(client, mode):
    name = f"{prefix()}-incidents-{stamp()}"
    client.create_dataset(name=name, description="Synthetic incidents; five test cases")
    for case in cases():
        client.create_dataset_item(
            dataset_name=name,
            id=str(uuid5(NAMESPACE_URL, name + "/" + case["id"])),
            input=case["inputs"],
            expected_output=case["outputs"],
            metadata={"case_id": case["id"]},
        )
    state("langfuse", dataset=name)
    print(f"Dataset: {name}")
    return name


def evaluator(*, output, expected_output, **kwargs):
    return [
        Evaluation(name=key, value=value)
        for key, value in score_answer(output["answer"], expected_output).items()
    ]


def run_evaluator(*, item_results, **kwargs):
    scores = [
        e.value for item in item_results for e in item.evaluations if e.name == "keyword_coverage"
    ]
    return Evaluation(name="mean_keyword_coverage", value=mean(scores) if scores else 0.0)


def evaluate(client, mode):
    name = state("langfuse").get("dataset")
    if not name or not name.startswith(prefix() + "-"):
        name = dataset(client, mode)
    ds = client.get_dataset(name)
    for variant in ("baseline", "good"):

        def task(*, item, v=variant, **kwargs):
            inputs = item["input"] if isinstance(item, dict) else item.input
            result, _ = pipeline(client, inputs, mode, v)
            return result

        result = ds.run_experiment(
            name=f"{prefix()}-{variant}",
            run_name=f"{variant}-{stamp()}",
            task=task,
            evaluators=[evaluator],
            run_evaluators=[run_evaluator],
            max_concurrency=2,
            metadata={"variant": variant, "model_mode": mode},
        )
        # Experiment runner isolates item failures; never silently label them as a full success.
        if len(result.item_results) != len(cases()):
            raise ValueError("일부 평가 항목이 실패했습니다. Experiments에서 오류를 확인하세요.")
        print(result.format())
        save_json(f"langfuse-{variant}.json", {"summary": result.format()})


def scores(client, mode):
    saved = state("langfuse")
    trace_id = saved.get("trace_id") or tracing(client, mode)
    client.create_score(
        trace_id=trace_id,
        name="demo-quality",
        value=0.8,
        data_type="NUMERIC",
        comment="합성 점수: 실제 사람 평가 아님",
    )
    client.create_score(trace_id=trace_id, name="demo-approved", value=1, data_type="BOOLEAN")
    client.create_score(
        trace_id=trace_id, name="demo-category", value="needs-review", data_type="CATEGORICAL"
    )
    client.create_score(session_id=state("langfuse")["session_id"], name="demo-session", value=1)
    print("숫자/불리언/범주형/세션 점수 생성")


def query(client, mode):
    client.flush()
    trace_id = state("langfuse").get("trace_id")
    if not trace_id:
        raise ValueError("먼저 langfuse trace --live를 실행하세요.")
    # SDK v5 uses Observations API v2; the old api.trace.list is removed.
    result = client.api.observations.get_many(
        trace_id=trace_id, limit=50, fields="core,basic,usage,io"
    )
    path = save_json("langfuse-observations.json", result.model_dump(mode="json"))
    print(f"관찰 데이터(최대 50개): {path}. 수집 지연 시 query를 다시 실행하세요.")


def integrations(client, mode):
    from langchain_core.runnables import RunnableLambda
    from langfuse.langchain import CallbackHandler

    question = cases()[0]["inputs"]["question"]
    handler = CallbackHandler()
    chain = RunnableLambda(retrieve).with_config(run_name="langchain-retriever")
    with client.start_as_current_observation(name="sdk-stream-and-langchain"):
        docs = chain.invoke(question, config={"callbacks": [handler]})
        with model_client("langfuse") as llm:
            with llm.chat.completions.create(
                model=os.environ["LLM_MODEL"],
                messages=messages(question, docs),
                stream=True,
                stream_options={"include_usage": True},
                max_tokens=256,
            ) as stream:
                for chunk in stream:
                    if chunk.choices:
                        print(chunk.choices[0].delta.content or "", end="", flush=True)
        print()


def media(client, mode):
    from langfuse.media import LangfuseMedia

    path = ROOT / "factory" / "data" / "status.png"
    if not path.exists():
        raise ValueError("먼저 python -m lab factory prepare를 실행하세요.")
    picture = LangfuseMedia(content_bytes=path.read_bytes(), content_type="image/png")
    with client.start_as_current_observation(name="image-input", input={"image": picture}) as span:
        span.update(output="멀티모달 첨부 실습입니다. 비전 모델 호출은 하지 않습니다.")
    print("PNG 미디어 첨부를 큐에 넣었습니다. 서버의 오브젝트 저장소 설정이 필요합니다.")


def judge_demo(client, mode):
    trace_id = tracing(client, mode)
    case = cases()[0]
    result = judge(
        case["inputs"]["question"], state("langfuse")["output"]["answer"], case["outputs"]
    )
    client.create_score(
        trace_id=trace_id, name="llm-judge", value=result["score"], comment=result["reason"]
    )
    print(result)


STEPS = {
    "trace": tracing,
    "async": async_demo,
    "prompts": prompts,
    "dataset": dataset,
    "evaluate": evaluate,
    "scores": scores,
    "query": query,
    "integrations": integrations,
    "media": media,
    "judge": judge_demo,
}


def run(step, mode):
    require_env("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
    client = Langfuse(mask=scrub, environment="lab", sample_rate=1.0)
    selected = ["trace", "async", "prompts", "dataset", "evaluate", "scores", "query", "media"]
    try:
        if not client.auth_check():
            raise ValueError("Langfuse 인증 실패: URL/키/서버 버전을 확인하세요.")
        for name in selected if step == "all" else [step]:
            print(f"\n[Langfuse / {name} / model={mode}]")
            STEPS[name](client, mode)
    finally:
        client.flush()
        client.shutdown()
    print("전송 처리를 마쳤습니다. 웹 화면에서 수집 여부와 결과를 확인하세요.")
