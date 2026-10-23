"""Check a remote Qwen/OpenAI-compatible endpoint without LangSmith or Langfuse."""

import os
import time

from dotenv import set_key
from openai import APIConnectionError, APIStatusError, APITimeoutError

from lab.common import (
    ROOT,
    messages,
    model_client,
    model_max_tokens,
    require_env,
    retrieve,
    save_json,
)


def discover(client, save_model=False):
    response = client.models.list()
    ids = [item.id for item in response.data]
    if not ids:
        raise ValueError("서버의 모델 목록이 비어 있습니다. 모델 로딩 상태를 확인하세요.")
    print("서버 모델:")
    for model_id in ids:
        print(f"  {model_id}")
    if save_model:
        if len(ids) != 1:
            raise ValueError(
                "모델이 여러 개입니다. 사용할 ID를 .env의 LLM_MODEL에 직접 지정하세요."
            )
        set_key(str(ROOT / ".env"), "LLM_MODEL", ids[0])
        os.environ["LLM_MODEL"] = ids[0]
        print("서버가 반환한 모델 ID를 .env의 LLM_MODEL에 저장했습니다.")
    return ids


def chat(client, question, stream=False):
    require_env("LLM_MODEL")
    started = time.monotonic()
    kwargs = {
        "model": os.environ["LLM_MODEL"],
        "messages": messages(question, retrieve(question)),
        "max_tokens": model_max_tokens(),
    }
    usage = None
    finish_reason = None
    if stream:
        pieces = []
        with client.chat.completions.create(
            **kwargs, stream=True, stream_options={"include_usage": True}
        ) as response:
            for chunk in response:
                if chunk.usage is not None:
                    usage = chunk.usage.model_dump()
                if chunk.choices:
                    choice = chunk.choices[0]
                    text = choice.delta.content or ""
                    pieces.append(text)
                    print(text, end="", flush=True)
                    finish_reason = choice.finish_reason or finish_reason
        output = "".join(pieces)
        print()
    else:
        response = client.chat.completions.create(**kwargs)
        if not response.choices:
            raise ValueError(
                "서버 응답에 choices가 없습니다. Chat Completions 호환성을 확인하세요."
            )
        output = response.choices[0].message.content or ""
        finish_reason = response.choices[0].finish_reason
        usage = response.usage.model_dump() if response.usage else None
        print(output)
    if not output.strip():
        raise ValueError(
            "서버가 빈 답변을 반환했습니다. 모델의 추론 토큰 예산과 chat template을 확인하세요."
        )
    report = {
        "mode": "api",
        "base_url": os.environ["LLM_BASE_URL"],
        "model": os.environ["LLM_MODEL"],
        "question": question,
        "answer": output,
        "stream": stream,
        "finish_reason": finish_reason,
        "usage": usage,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    path = save_json("model-report.json", report)
    print(f"실제 모델 응답 저장: {path}")
    if finish_reason == "length":
        print("응답이 토큰 한도에 도달했습니다. 완결된 응답인지 확인하세요.")
    return report


def run(args):
    try:
        with model_client() as client:
            if args.step == "models":
                return discover(client, args.save_model)
            return chat(client, args.question, args.stream)
    except APIStatusError as exc:
        if exc.status_code == 401 and "INVALIDCOOKIE" in exc.response.text:
            raise ValueError(
                "HTTP 401 INVALIDCOOKIE: 이 주소는 브라우저 세션 인증을 요구합니다. "
                "브라우저 로그인은 Python에 적용되지 않습니다. "
                "API 전용 주소/인증 또는 승인된 SSH 터널을 사용하세요. docs/KTCLOUD.md 참고."
            ) from None
        if exc.status_code in {401, 403}:
            raise ValueError(
                f"HTTP {exc.status_code}: 모델 서버/프록시의 API 인증 설정을 확인하세요."
            ) from None
        raise ValueError(
            f"모델 서버 HTTP {exc.status_code}: URL·모델 ID·요청 형식과 서버 로그를 확인하세요."
        ) from None
    except APITimeoutError:
        raise ValueError(
            "모델 응답 시간 초과: 서버 상태를 확인하고 LLM_TIMEOUT을 조정하세요."
        ) from None
    except APIConnectionError:
        raise ValueError(
            "모델 서버에 연결할 수 없습니다. LLM_BASE_URL, SSH 터널, 서버 수신 포트를 확인하세요."
        ) from None
