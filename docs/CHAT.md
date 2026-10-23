# 일반 채팅과 도구 호출

## 바로 실행

ktcloud SSH 터널이 연결된 상태에서 `.venv`를 활성화하고 실행합니다.

```powershell
python -m lab chat --live --stream
```

일상 질문, 코딩, 번역 등 자유롭게 질문할 수 있습니다. 장애 문서 검색과 `원인/조치/근거`
출력 형식은 사용하지 않습니다. 서버와 모델은 `.env`의 `LLM_*` 설정을 그대로 사용합니다.

- `/exit`: 대화 종료. Ctrl+C 또는 입력 종료로도 나올 수 있습니다.
- `/reset`: 새 세션을 시작하고 이전 대화를 모델에 보내지 않습니다.
- 최근 20개 질문·답변 쌍을 후속 질문에 함께 전송합니다. 프로그램 재실행 시 새 대화입니다.
- 긴 질문·답변은 서버의 컨텍스트 한도를 넘을 수 있습니다. `/reset`하거나 입력을 줄이세요.
- 매 응답 후 `artifacts/chat-<세션ID>.json`에 대화·처리 시간·실제 사용량을 저장합니다.
  로컬 파일에는 대화 원문이 저장되고 Git에서는 제외됩니다. 이전 세션 자동 복원은 하지 않습니다.
- 출력이 잘리면 `.env`의 `LLM_MAX_TOKENS`를 늘립니다. Qwen의 추론 토큰도 이 한도에 포함됩니다.

한 번만 질문하려면:

```powershell
python -m lab chat --live --stream --question "파이썬 리스트와 튜플의 차이를 알려줘"
```

기존 `python -m lab model chat --live`는 장애 분석 예제입니다.

## LangSmith와 Langfuse 기록

| 옵션 | 기록 위치 | 필요한 설정 |
|---|---|---|
| 생략 또는 `--trace none` | 로컬 JSON | 모델 연결 |
| `--trace langsmith` | 로컬 JSON + LangSmith | LANGSMITH_API_KEY, 프로젝트/endpoint |
| `--trace langfuse` | 로컬 JSON + Langfuse | 실행 중인 서비스, LANGFUSE_BASE_URL/PUBLIC_KEY/SECRET_KEY |
| `--trace both` | 로컬 JSON + 두 서비스 | 두 서비스 모두 설정 |

```powershell
python -m lab chat --live --stream --trace langfuse
python -m lab chat --live --stream --trace langsmith
python -m lab chat --live --stream --trace both
```

질문·전달된 이전 대화·답변·모델·사용량·오류가 `general-chat` 기록에 남습니다.
두 서비스를 선택해도 모델은 질문당 한 번만 호출합니다.
같은 대화는 동일한 session ID를 사용합니다. JSON의 `trace_ids`로 각 기록을 찾을 수 있습니다.
이메일 및 일부 민감 키 이름에 예제 마스킹을 적용하지만 완전한 개인정보 필터는 아닙니다.
응답 시간과 토큰 수는 확인할 수 있으며 자체 호스팅 Qwen의 금액 비용은 자동 산정하지 않습니다.
일반 채팅에는 장애 분석용 점수를 자동 부여하지 않습니다.

기록 전송 완료 안내만으로 서버 수집 성공을 보장하지 않습니다. 대시보드에서 trace ID와
내용을 확인하세요. 설정된 서비스가 연결되지 않으면 주소·인증·실행 상태를 확인합니다.
서버 준비 방법은 [Langfuse 안내](LANGFUSE.md), [LangSmith 안내](LANGSMITH.md)를 참고하세요.

2026-10-23 검증 환경에서는 일반 Qwen 응답과 두 SDK의 로컬 테스트를 통과했습니다.
LangSmith 키는 미설정이고, 로컬 Langfuse는 연결 거부 상태입니다.
Docker Desktop 시작 요청 후에도 엔진 API가 HTTP 500을 반환하여 실제 서버 수집은 아직 확인하지 못했습니다.
Docker 엔진이 정상화되면 기존 구성을 시작하고 위 `--trace langfuse` 명령으로 실행합니다.

```powershell
docker compose --env-file infra/.env -f infra/compose.yaml up -d
```

## 웹 검색·서버 실행을 추가하려면

현재 일반 채팅에는 외부 행동 도구를 등록하지 않았습니다. 도구를 사용하려면 다음을 연결합니다.

1. **Tool**: 검색 API를 호출하는 `web_search(query)`나 SSH로 정해진 상태 명령을 실행하는
   `server_status(target)` 같은 함수. 직접 구현하거나 기존 LangChain/MCP 도구를 사용할 수 있습니다.
2. **Tool Calling**: 모델에 함수 이름·설명·입력 형식을 알려주고, 모델이 어떤 함수를 어떤
   인자로 호출할지 구조화된 요청을 생성하게 합니다.
3. **실행 루프**: 프로그램이 인자를 검증하고 허용된 함수를 실행한 뒤 결과를 모델에 전달합니다.
   모델이 결과를 읽고 추가 호출 또는 최종 답변을 결정합니다. 반복 횟수와 시간 제한을 둡니다.
4. **관찰**: LangSmith/Langfuse에서 모델 판단, 도구 입력·출력, 시간과 오류를 기록합니다.

```text
질문 → Qwen → tool_calls → 입력 검증·도구 실행 → 결과를 Qwen에 전달 → 답변
                ↑                                 │
                └──────── 추가 호출 필요 시 ───────┘
```

LangGraph는 필수가 아닙니다. 간단한 도구 호출 루프는 Python으로도 구현할 수 있습니다.
LangGraph는 조건 분기, 반복, 상태 저장, 실패 후 재개, 사람의 승인 같은 흐름을 관리할 때 유용합니다.
서버 작업은 처음에는 GPU/CPU/메모리 조회 등 허용된 읽기 명령으로 구성하고, 변경 작업은
별도 권한·승인 단계를 두는 구조가 적합합니다. 모델이 만든 임의 문자열을 그대로 셸에 넘기지 않습니다.

ktcloud의 현재 일반 Chat Completions 연결 성공만으로 Tool Calling 지원까지 확인된 것은 아닙니다.
추가 시 Qwen 모델의 도구 사용 능력과 vLLM의 tool parser/chat template 설정을 함께 검증해야 합니다.

공식 문서: [LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools),
[LangGraph 개요](https://docs.langchain.com/oss/python/langgraph/overview).
