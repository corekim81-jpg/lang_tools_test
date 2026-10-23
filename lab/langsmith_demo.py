"""LangSmith: traces, async, prompts, datasets, experiments, feedback and SDK integration."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from statistics import mean
from uuid import uuid4

from langsmith import Client, trace, traceable, tracing_context
from langsmith.evaluation import evaluate_comparative

from lab.common import (
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


@traceable(run_type="retriever", name="knowledge-search")
def search(question: str):
    return retrieve(question)


@traceable(run_type="chain", name="incident-answer")
def pipeline(inputs: dict, mode="mock", variant="good"):
    docs = search(inputs["question"])
    # The mock is not labelled as a real LLM generation and has no invented token counts.
    with trace(
        "mock-generation" if mode == "mock" else "model-generation",
        run_type="llm",
        inputs={"messages": messages(inputs["question"], docs)},
        metadata={"simulation": mode == "mock", "variant": variant},
    ) as run:
        text = generate(inputs["question"], docs, mode=mode, variant=variant, tool="langsmith")
        run.end(outputs={"answer": text})
    return {"answer": text}


def tracing(client: Client, mode: str) -> str:
    run_id = uuid4()
    session = f"{prefix()}-{stamp()}"
    with trace(
        "incident-session",
        run_id=run_id,
        inputs=scrub(
            {
                "question": cases()[0]["inputs"]["question"],
                "contact": "demo@example.com",
            }
        ),
        metadata={"session_id": session, "user_id": "demo-user", "model_mode": mode},
        tags=["lab", "rag", mode],
    ) as root:
        output = pipeline(cases()[0]["inputs"], mode)
        root.end(outputs=output)
    try:
        with trace("intentional-error", inputs={"synthetic": True}):
            raise RuntimeError("실습용 검색 타임아웃 (의도한 오류)")
    except RuntimeError:
        pass
    client.flush()
    state("langsmith", run_id=str(run_id), output=output, session_id=session)
    print(f"Trace ID: {run_id} (정상 실행 + 의도한 오류, 세션/사용자/태그)")
    return str(run_id)


def async_demo(client, mode):
    @traceable(name="async-incident")
    async def task(inputs):
        return await asyncio.to_thread(pipeline, inputs, mode)

    async def batch():
        return await asyncio.gather(*(task(case["inputs"]) for case in cases()[:2]))

    print(asyncio.run(batch()))


def prompts(client, mode):
    from langchain_core.prompts import ChatPromptTemplate

    name = f"{prefix()}-incident"
    for version, instruction in (("v1", "장애 질문에 짧게 답하세요."), ("v2", SYSTEM)):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", instruction),
                ("human", "근거: {context}\n질문: {question}"),
            ]
        )
        url = client.push_prompt(
            name, object=prompt, is_public=False, commit_description=f"Lab {version}", tags=["lab"]
        )
        print(f"{version}: {url}")
    pulled = client.pull_prompt(name)
    print(pulled.invoke({"context": "CPU 사용률 점검 문서", "question": "CPU가 높아요"}))
    state("langsmith", prompt=name)


def dataset(client, mode):
    name = f"{prefix()}-incidents-{stamp()}"
    ds = client.create_dataset(
        dataset_name=name, description="Synthetic incidents; five test cases"
    )
    client.create_examples(
        dataset_id=ds.id,
        examples=[
            {
                "inputs": c["inputs"],
                "outputs": c["outputs"],
                "metadata": {"case_id": c["id"]},
                "split": "test",
            }
            for c in cases()
        ],
    )
    client.update_dataset_tag(dataset_id=ds.id, as_of=datetime.now(timezone.utc), tag="baseline")
    state("langsmith", dataset=name, dataset_id=str(ds.id))
    print(f"Dataset: {name}; split=test; version tag=baseline")
    return name


def ensure_dataset(client, mode):
    saved = state("langsmith").get("dataset")
    return saved if saved and saved.startswith(prefix() + "-") else dataset(client, mode)


def evaluator(run, example):
    values = score_answer((run.outputs or {}).get("answer", ""), example.outputs)
    return {"results": [{"key": key, "score": value} for key, value in values.items()]}


def summary(runs, examples):
    values = [
        score_answer((r.outputs or {}).get("answer", ""), e.outputs)["keyword_coverage"]
        for r, e in zip(runs, examples)
    ]
    return {"key": "mean_keyword_coverage", "score": mean(values) if values else 0.0}


def evaluate(client, mode):
    name = ensure_dataset(client, mode)
    experiments = []
    for variant in ("baseline", "good"):
        result = client.evaluate(
            lambda inputs, v=variant: pipeline(inputs, mode, v),
            data=name,
            evaluators=[evaluator],
            summary_evaluators=[summary],
            experiment_prefix=f"{prefix()}-{variant}",
            max_concurrency=2,
            metadata={"variant": variant, "model_mode": mode},
        )
        rows = list(result)
        if len(rows) != len(cases()) or any(row["run"].error for row in rows):
            raise ValueError("평가 실행 일부가 실패했습니다. 서비스의 실험 결과를 확인하세요.")
        experiments.append(result.experiment_name)
        save_json(
            f"langsmith-{variant}.json",
            [
                {
                    "run_id": str(row["run"].id),
                    "outputs": row["run"].outputs,
                    "feedback": row["evaluation_results"],
                }
                for row in rows
            ],
        )
        print(f"Experiment: {result.experiment_name} ({len(rows)} cases)")
    state("langsmith", experiments=experiments)


def comparison(runs, example):
    return {
        "key": "pairwise_keyword_coverage",
        "scores": {
            str(run.id): score_answer((run.outputs or {}).get("answer", ""), example.outputs)[
                "keyword_coverage"
            ]
            for run in runs
        },
    }


def compare(client, mode):
    experiments = state("langsmith").get("experiments")
    if not experiments:
        evaluate(client, mode)
        experiments = state("langsmith")["experiments"]
    result = evaluate_comparative(
        tuple(experiments),
        evaluators=[comparison],
        client=client,
        experiment_prefix=f"{prefix()}-pairwise",
        max_concurrency=2,
    )
    print(f"비교 평가 완료: {type(result).__name__}; Experiments에서 확인하세요.")


def feedback(client, mode):
    run_id = state("langsmith").get("run_id") or tracing(client, mode)
    client.create_feedback(
        run_id,
        key="demo-human-feedback",
        score=1,
        comment="예제 프로그램이 넣은 합성 피드백; 실제 사람 평가가 아님",
    )
    queue = client.create_annotation_queue(
        name=f"{prefix()}-review-{stamp()}",
        description="실행을 열고 원인/조치/근거를 사람이 검토하는 실습",
        rubric_instructions="근거 문서 일치 여부와 조치 적절성을 확인하세요.",
    )
    client.add_runs_to_annotation_queue(queue.id, run_ids=[run_id])
    print(f"Feedback + annotation queue: {queue.id}")


def query(client, mode):
    client.flush()
    rows = list(
        client.list_runs(
            project_name=os.getenv("LANGSMITH_PROJECT", prefix()), is_root=True, limit=20
        )
    )
    path = save_json(
        "langsmith-runs.json",
        [
            {
                "id": str(r.id),
                "name": r.name,
                "error": r.error,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "total_tokens": r.total_tokens,
            }
            for r in rows
        ],
    )
    print(f"최대 20개 실행 조회: {path}. 수집 지연 시 query를 다시 실행하세요.")


def integrations(client, mode):
    from langchain_core.runnables import RunnableLambda

    # Native LangChain tracing inherits the explicit tracing context below.
    chain = RunnableLambda(retrieve).with_config(run_name="langchain-retriever")
    question = cases()[0]["inputs"]["question"]
    with trace("sdk-stream-and-langchain", inputs={"question": question}):
        docs = chain.invoke(question)
        with model_client("langsmith") as llm:
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


def judge_demo(client, mode):
    run_id = tracing(client, mode)
    case = cases()[0]
    result = judge(
        case["inputs"]["question"], state("langsmith")["output"]["answer"], case["outputs"]
    )
    client.create_feedback(run_id, key="llm-judge", score=result["score"], comment=result["reason"])
    print(result)


STEPS = {
    "trace": tracing,
    "async": async_demo,
    "prompts": prompts,
    "dataset": dataset,
    "evaluate": evaluate,
    "compare": compare,
    "feedback": feedback,
    "query": query,
    "integrations": integrations,
    "judge": judge_demo,
}


def run(step, mode):
    require_env("LANGSMITH_API_KEY")
    client = Client(hide_inputs=scrub, hide_outputs=scrub)
    project = os.getenv("LANGSMITH_PROJECT", prefix())
    selected = ["trace", "async", "prompts", "dataset", "evaluate", "compare", "feedback", "query"]
    try:
        with tracing_context(enabled=True, client=client, project_name=project):
            for name in selected if step == "all" else [step]:
                print(f"\n[LangSmith / {name} / model={mode}]")
                STEPS[name](client, mode)
    finally:
        client.flush()
    print("전송 처리를 마쳤습니다. 웹 화면에서 수집 여부와 결과를 확인하세요.")
