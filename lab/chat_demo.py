"""General conversation with optional LangSmith and Langfuse observations."""

import os
from contextlib import ExitStack, contextmanager
from uuid import uuid4

from lab.common import model_client, model_max_tokens, require_env, save_json, scrub
from lab.model_demo import chat

GENERAL_SYSTEM = (
    "당신은 친절하고 정확한 AI 도우미입니다. 사용자의 언어로 자연스럽게 답하세요. "
    "질문의 성격에 맞게 설명하고, 모르는 내용은 모른다고 말하세요. "
    "웹 검색이나 서버 실행 도구는 연결되어 있지 않습니다. "
    "실제로 검색하거나 명령을 실행했다고 주장하지 마세요."
)
HISTORY_TURNS = 20


def general_messages(history, question):
    return [
        {"role": "system", "content": GENERAL_SYSTEM},
        *history[-HISTORY_TURNS * 2 :],
        {"role": "user", "content": question},
    ]


@contextmanager
def observers(selection):
    # Validate every selected service before opening a connection or calling the model.
    if selection in {"langsmith", "both"}:
        require_env("LANGSMITH_API_KEY")
    if selection in {"langfuse", "both"}:
        require_env("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
    with ExitStack() as stack:
        ls = lf = None
        if selection in {"langsmith", "both"}:
            from langsmith import Client, tracing_context

            ls = Client(hide_inputs=scrub, hide_outputs=scrub)
            stack.callback(ls.flush)
            stack.enter_context(
                tracing_context(
                    enabled=True,
                    client=ls,
                    project_name=os.getenv("LANGSMITH_PROJECT", "lang-tools-lab"),
                )
            )
        if selection in {"langfuse", "both"}:
            from langfuse import Langfuse

            lf = Langfuse(mask=scrub, environment="lab", sample_rate=1.0, timeout=10)
            stack.callback(lf.shutdown)
            stack.callback(lf.flush)
            import httpx

            try:
                authenticated = lf.auth_check()
            except httpx.HTTPError:
                raise ValueError(
                    "Langfuse에 연결할 수 없습니다. "
                    "서버 실행 상태와 LANGFUSE_BASE_URL을 확인하세요."
                ) from None
            if not authenticated:
                raise ValueError("Langfuse 인증 실패: URL/키/서버 실행 상태를 확인하세요.")
        yield ls, lf


@contextmanager
def record_turn(request_messages, session_id, report, ls=None, lf=None):
    """Both destinations observe one model call; no duplicate inference."""
    with ExitStack() as stack:
        ls_run = lf_span = None
        if ls is not None:
            from langsmith import trace

            ls_run = stack.enter_context(
                trace(
                    "general-chat",
                    run_type="llm",
                    client=ls,
                    inputs={"messages": request_messages},
                    metadata={
                        "session_id": session_id,
                        "ls_provider": "vllm",
                        "ls_model_name": os.environ["LLM_MODEL"],
                        "ls_model_type": "chat",
                    },
                )
            )
        if lf is not None:
            from langfuse import propagate_attributes

            stack.enter_context(propagate_attributes(session_id=session_id))
            lf_span = stack.enter_context(
                lf.start_as_current_observation(
                    name="general-chat",
                    as_type="generation",
                    input=request_messages,
                    model=os.environ["LLM_MODEL"],
                    model_parameters={"max_tokens": model_max_tokens()},
                )
            )
        yield
        usage = report.get("usage") or {}
        tokens = {
            target: usage[source]
            for source, target in (
                ("prompt_tokens", "input_tokens"),
                ("completion_tokens", "output_tokens"),
                ("total_tokens", "total_tokens"),
            )
            if usage.get(source) is not None
        }
        report["trace_ids"] = {}
        if ls_run is not None:
            ls_run.end(
                outputs={
                    "message": {"role": "assistant", "content": report["answer"]},
                    "usage_metadata": tokens,
                    "finish_reason": report["finish_reason"],
                }
            )
            report["trace_ids"]["langsmith"] = str(ls_run.id)
        if lf_span is not None:
            lf_span.update(
                output=report["answer"],
                usage_details={
                    name.removesuffix("_tokens"): value for name, value in tokens.items()
                },
                metadata={"finish_reason": report["finish_reason"]},
            )
            report["trace_ids"]["langfuse"] = lf_span.trace_id


def run(args):
    require_env("LLM_MODEL")
    session_id = str(uuid4())
    history, turns = [], []
    one_shot = args.question is not None
    with observers(args.trace) as (ls, lf), model_client() as client:
        print(f"일반 채팅 | 모델: {os.environ['LLM_MODEL']} | 기록: {args.trace}")
        if not one_shot:
            print("질문을 입력하세요. /exit 종료, /reset 새 대화 (최근 20턴을 모델에 전달)")
        while True:
            try:
                question = args.question if one_shot else input("\n나> ")
            except (EOFError, KeyboardInterrupt):
                print("\n대화를 종료합니다.")
                break
            question = question.strip()
            if not question:
                if one_shot:
                    raise ValueError("질문을 입력하세요.")
                continue
            if not one_shot and question == "/exit":
                break
            if not one_shot and question == "/reset":
                session_id, history, turns = str(uuid4()), [], []
                print("새 대화를 시작했습니다.")
                continue
            request_messages = general_messages(history, question)
            report = {}
            print("\nQwen> ", end="", flush=True)
            try:
                with record_turn(request_messages, session_id, report, ls, lf):
                    report.update(
                        chat(
                            client,
                            question,
                            args.stream,
                            request_messages=request_messages,
                            report_name=None,
                        )
                    )
            except KeyboardInterrupt:
                print("\n응답을 중단하고 대화를 종료합니다.")
                break
            history.extend(
                [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": report["answer"]},
                ]
            )
            report.update(chat_mode="general", session_id=session_id, tracing=args.trace)
            turns.append(report)
            path = save_json(f"chat-{session_id}.json", {"session_id": session_id, "turns": turns})
            print(f"대화 저장: {path}")
            if one_shot:
                break
    if args.trace != "none":
        print("기록 전송 처리를 마쳤습니다. 대시보드에서 trace ID로 수집 여부를 확인하세요.")
    return turns
