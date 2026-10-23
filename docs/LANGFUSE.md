# Langfuse 실습

코드: `lab/langfuse_demo.py`. Python SDK 5.0.4 / 서버 4.59.0 이상을 대상으로 합니다.

## 서버 선택

Cloud와 로컬 서버는 `.env`의 `LANGFUSE_BASE_URL`과 키만 다릅니다.
로컬 서버는 루트 README의 초기화 및 Compose 명령으로 시작합니다.
공식 배포 구성을 바탕으로 web/worker/PostgreSQL/Redis/ClickHouse/MinIO를 구성했습니다.
모든 공개 포트는 localhost에 바인딩합니다. 실습용 단일 서버 구성입니다.

```powershell
docker compose --env-file infra/.env -f infra/compose.yaml logs --tail 50 langfuse-web langfuse-worker
```

웹 서비스 준비 후 [localhost:3000](http://localhost:3000)에 로그인합니다.
자격 증명은 `infra/.env`에 저장되며 Git에서 제외됩니다. 초기화 스크립트는 기존 파일을 덮어쓰지 않습니다.
서버 종료 시 데이터를 보존하려면:

```powershell
docker compose --env-file infra/.env -f infra/compose.yaml down
```

## 실행 목록

`python -m lab langfuse <step> --live`로 선택합니다.

| step | 확인할 기능 | 기대 결과 |
|---|---|---|
| `trace` | agent/retriever/generation/tool, context manager, 수동 종료, 오류 | 중첩 observations, 동일 session의 두 질문, 오류 trace |
| `async` | observe decorator, asyncio, thread context | 비동기 chain 2개와 하위 실행 |
| `prompts` | text/chat, 버전, 라벨, cache, compile, 생성 연결 | lab-tested 라벨과 prompt-linked-generation |
| `dataset` | 데이터셋과 항목 생성 | 5개 합성 장애 사례 |
| `evaluate` | hosted dataset runner, 개별/집계 evaluator, A/B | baseline/good 실험과 점수 |
| `scores` | NUMERIC/BOOLEAN/CATEGORICAL, session score | trace와 session에 합성 점수 |
| `query` | Observations API v2 | artifacts/langfuse-observations.json |
| `integrations` | LangChain callback + 모델 SDK + streaming | 실제 모델 호출 usage; `--model api` 필요 |
| `media` | PNG 미디어 업로드 | 합성 패널 이미지가 있는 observation |
| `judge` | 모델 평가자 | LLM 평가 점수; `--model api` 필요 |
| `all` | 기본 단계 묶음 | integrations/judge 제외한 모든 단계 |

미디어는 실제 비전 모델 호출 없이 첨부 기능만 검사합니다.
비전 학습은 `factory/configs/multimodal.yaml`에서 별도로 실습합니다.
`factory prepare`를 수행하지 않은 새 복사본에서는 먼저 해당 명령을 실행하세요.

## 화면에서 확인하기

1. Observations/Traces에서 incident-agent → knowledge-search/mock-generation을 펼칩니다.
2. Sessions에서 두 질문이 동일 session_id에 들어가는지 확인합니다.
3. manual-tool의 연락처가 `[EMAIL]`, api_key가 `[REDACTED]`인지 확인합니다.
4. Prompts에서 text v1/v2, chat prompt, lab-tested 라벨을 확인합니다.
5. 연결된 generation에서 프롬프트 버전으로 이동합니다.
6. Datasets/Experiments에서 baseline/good의 keyword/format/reference 점수를 비교합니다.
7. Scores에서 숫자/불리언/범주형 점수를 확인합니다. 프로그램이 만든 합성 점수입니다.
8. image-input을 열어 이미지가 표시되는지 확인합니다.

## 웹 기능 확장 실습

- **온라인 평가:** 프로젝트 평가 설정에서 lab 환경의 observation에만 적용하는 평가자를
  만들고 샘플링 비율을 지정합니다. 모델 연결 후 새 trace에 자동 점수가 붙는지 확인합니다.
- **사람 평가:** annotation queue 또는 점수 입력 화면에서 테스트 실행에 실제 점수를 넣습니다.
- **대시보드:** 사용자/세션/모델 기준 latency, usage, cost를 비교합니다.
- **커스텀 가격:** 로컬 모델의 실제 비용 기준이 있으면 모델/가격 설정에 입력하고
  integrations를 실행해 usage에 따른 계산을 확인합니다. 가격 미설정 시 비용 0은 무료의 증거가 아닙니다.
- **라벨 롤백:** lab-tested를 v1으로 옮긴 뒤 캐시 만료 후 get_prompt 결과를 확인합니다.
- **데이터 버전:** 항목 수정 전후 시각으로 `client.get_dataset(name, version=timestamp)`를 조회합니다.
- **보관/권한/SSO:** 테스트 조직에서 두 계정의 접근 결과를 비교합니다. 요금제/권한 조건은 별도 확인합니다.

## 오류 해석

- SDK 5로 서버 v3에 연결: 제공한 서버 v4 또는 해당 서버에 맞는 이전 SDK가 필요합니다.
- 401/403: 두 키가 동일 프로젝트인지, base URL 리전이 맞는지 확인합니다.
- 미디어가 비어 있음: MinIO 상태, localhost:9090, web의 외부 미디어 endpoint를 확인합니다.
- query 결과가 비어 있음: exporter/worker 로그를 보고 수집 반영 후 재실행합니다.
- 상태 파일은 이전 프로젝트의 ID를 기억합니다. 프로젝트 변경 시 해당 state 파일을 다른 이름으로 옮깁니다.
- 모델 API가 stream_options를 거부하면 해당 엔드포인트의 호환성을 확인하세요.

공식 SDK: https://langfuse.com/docs/observability/sdk/overview
