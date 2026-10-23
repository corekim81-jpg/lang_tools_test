# LangSmith 실습

코드: `lab/langsmith_demo.py`. 모든 명령은 프로젝트 루트에서 실행합니다.

## 준비

1. LangSmith에 실습용 프로젝트를 만들고 API key를 발급합니다.
2. `.env`의 `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, 리전에 맞는 `LANGSMITH_ENDPOINT`를 설정합니다.
3. 조직 키에 workspace 지정이 필요하면 `LANGSMITH_WORKSPACE_ID`를 설정합니다.
4. `python -m lab langsmith trace --live`로 첫 실행을 만듭니다.

## 실행 목록

`python -m lab langsmith <step> --live`로 아래 단계를 선택합니다.

| step | 확인할 기능 | 기대 결과 |
|---|---|---|
| `trace` | context/decorator, RAG 계층, metadata, tag, 마스킹, 오류 | incident-session → incident-answer → 검색/생성; 별도 intentional-error |
| `async` | asyncio + worker thread의 추적 문맥 전파 | 2개 비동기 실행의 자식 추적 |
| `prompts` | private prompt push/pull, 버전, 템플릿 | 같은 이름에 v1/v2 커밋과 치환된 질문 |
| `dataset` | 데이터셋·사례·split·버전 태그 | 5개 사례, test split, baseline tag |
| `evaluate` | custom/summary evaluator, 동시성, baseline/good 실험 | 두 실험과 3가지 점수, 평균 점수 |
| `compare` | 쌍 비교 평가 | 동일 사례의 두 응답에 keyword coverage 점수 |
| `feedback` | 피드백 API, annotation queue | 합성 피드백 1개와 사람 검토용 큐 |
| `query` | 실행 조회·토큰 정보·JSON 내보내기 | artifacts/langsmith-runs.json |
| `integrations` | LangChain, 모델 SDK wrapper, streaming | 실제 모델 스트림과 호출 usage; `--model api` 필요 |
| `judge` | LLM-as-a-judge | 모델이 생성한 score/reason; `--model api` 필요 |
| `all` | 기본 단계 묶음 | integrations/judge 제외한 모든 단계 |

`evaluate`는 데이터셋이 없으면 만듭니다. `compare`는 실험이 없으면 먼저 평가합니다.
`feedback`은 추적 ID가 없으면 먼저 추적을 생성합니다.
동일 프로젝트에서 이어 실행하는 것을 전제로 state 파일을 사용합니다.

## 화면에서 확인하기

1. Tracing project에서 `incident-session`을 열고 검색 문서와 응답의 `KB-CPU`를 대조합니다.
2. `intentional-error`를 열어 오류 메시지와 실패 필터를 확인합니다.
3. metadata에서 session/user ID, tags에서 mock/api를 확인합니다.
4. Datasets & Experiments에서 새 데이터셋의 두 실험을 비교합니다.
5. keyword_coverage/format/reference 점수를 확인합니다. mock good=1은 규칙 기반 예제입니다.
6. Prompts에서 두 커밋을 비교하고 Playground에서 변수를 넣어 봅니다.
7. Annotation Queues에서 생성된 큐의 실행을 열고 실제 사람이 평가를 추가합니다.

## 웹 기능 확장 실습

- **온라인 evaluator:** 프로젝트의 자동화/평가 규칙에서 lab 실행에만 적용할 평가자를
  만들고 샘플링 비율을 지정합니다. trace를 다시 실행한 후 점수가 생기는지 확인합니다.
  코드의 `judge`는 동기 평가 예제이며 서버의 자동 평가 규칙을 생성하지 않습니다.
- **대시보드:** error rate, latency, token/cost를 선택하고 intentional-error를 포함/제외합니다.
  비용은 실제 모델 usage와 지원되는 가격 매핑이 있어야 의미가 있습니다.
- **프롬프트 환경 승격:** lab 프롬프트의 커밋에 테스트 태그를 붙이고
  `client.pull_prompt("프롬프트이름:태그")`로 불러옵니다.
- **데이터 변경 이력:** UI에서 한 사례의 정답을 수정하고 baseline 태그와 현재 버전을 비교합니다.
- **배포·Gateway·권한:** [기능 점검표](FEATURE_MATRIX.md)의 추가 준비 항목을 따릅니다.

## 오류 해석

- 401/403: key, 리전 endpoint, workspace, 해당 기능의 권한을 확인합니다.
- 토큰 정보가 비어 있음: mock에서는 정상입니다. API 모드에서 usage 반환 여부를 확인합니다.
- 조회 결과가 바로 보이지 않음: 수집이 반영된 뒤 `query`를 다시 실행합니다.
- all 중간 단계 실패: 이미 생성한 결과는 유지됩니다. 문제를 수정하고 해당 step만 실행할 수 있습니다.
- 마스킹은 이메일 및 특정 키의 예제입니다. 운영 데이터에 대한 완전한 개인정보 탐지기는 아닙니다.

공식 API: https://reference.langchain.com/python/langsmith
