# LangSmith · Langfuse · LLaMA-Factory 실습실

공통 **장애 분석 도우미**를 사용해 관찰 → 평가 → 학습 → 추론을 실습합니다.
현재 폴더에서 실행하는 Python 프로젝트이며 한국어 예제 데이터가 포함되어 있습니다.

저장소: [corekim81-jpg/lang_tools_test](https://github.com/corekim81-jpg/lang_tools_test)

새 PC에서 시작하려면 저장소를 받은 뒤 아래 설치 절차를 실행하세요.
가상환경, 실제 API 키, 실행 결과는 GitHub에 포함하지 않습니다.

```powershell
git clone https://github.com/corekim81-jpg/lang_tools_test.git
cd lang_tools_test
python -m pip install uv
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

| 도구 | 준비된 실습 |
|---|---|
| LangSmith | 계층 추적, 오류, 비동기, 세션, 마스킹, 프롬프트 버전, 데이터셋·버전 태그, 평가, A/B·쌍 비교, 피드백·검토 큐, 조회, LangChain 연동, 스트리밍, LLM 평가자 |
| Langfuse | observation 종류, 수동/자동/비동기 추적, 세션·사용자, 마스킹, 프롬프트 버전·라벨·캐시, 데이터셋, 실험 비교, 점수, 조회, LangChain 연동, 스트리밍, 미디어, LLM 평가자, 로컬 서버 |
| LLaMA-Factory | 33개 설정: PT/SFT/RM/PPO/DPO/KTO/ORPO/SimPO, LoRA/QLoRA/Full/Freeze/OFT, LoRA 변형, CPU, 멀티모달, 평가, 체크포인트, 분산 학습, 병합, 채팅, API, vLLM |

**범위:** 주요 개발 기능에는 실행 예제를, 웹 화면·기업용 관리 기능에는 수동 점검 시나리오를 제공합니다.
제품의 모든 API, 모델, 하드웨어, 요금제 조합을 자동 검증한 프로젝트는 아닙니다.
정확한 구현 범위와 추가 조건은 [기능 점검표](docs/FEATURE_MATRIX.md)에 구분했습니다.

## 1. 바로 시작 — 키·GPU 없이

현재 작업 환경에는 `.venv`와 의존성 설치를 준비했습니다. PowerShell에서:

```powershell
Set-Location D:\AI\src\lang_tools_test
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m lab offline
.\.venv\Scripts\python.exe -m lab factory validate
```

새 환경에서는 Python 3.11 또는 3.12와 `uv`를 준비하고 아래를 먼저 실행합니다.

```powershell
python -m pip install uv
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Linux/WSL에서는 `bash scripts/setup.sh`를 사용합니다. `uv.lock`으로 버전을 고정했습니다.
이하 예제의 `python`은 `.venv`를 활성화한 Python을 뜻합니다.

```powershell
.\.venv\Scripts\Activate.ps1
python -m lab doctor
python -m lab --help
```

활성화가 차단되면 `python` 대신 `.\.venv\Scripts\python.exe`를 사용하세요.

`offline` 결과는 `artifacts/offline-report.json`에 저장됩니다.
baseline의 점수는 0, good은 1이 되도록 만든 결정적 규칙 예제입니다.
이는 평가 흐름 학습용이며 실제 모델의 정확도가 100%라는 뜻이 아닙니다.

## 2. LangSmith

`.env.example`을 `.env`로 복사하고 `LANGSMITH_API_KEY`, 프로젝트 이름, 해당 리전의 endpoint를 설정합니다.
설정 여부만 보려면 `python -m lab doctor`를 실행하세요. 키 값은 출력하지 않습니다.

```powershell
python -m lab langsmith all --live
```

실제 LangSmith에 합성 데이터와 실행 기록을 생성하지만, 기본 응답 모델은 로컬 mock입니다.
LLM 제공자 키 없이도 추적·데이터셋·평가 기능을 실습할 수 있습니다.

```powershell
python -m lab langsmith trace --live
python -m lab langsmith prompts --live
python -m lab langsmith evaluate --live
python -m lab langsmith compare --live
python -m lab langsmith feedback --live
python -m lab langsmith query --live
```

실행별 기대 결과와 웹 화면 확인법: [LangSmith 안내](docs/LANGSMITH.md).

## 3. Langfuse

Cloud를 사용한다면 `.env`에 프로젝트의 public/secret key와 해당 리전의 base URL을 설정합니다.
로컬 서버를 사용한다면 Docker Desktop의 Linux 엔진을 켜고 아래를 실행합니다.

```powershell
python scripts/init_langfuse.py
docker compose --env-file infra/.env -f infra/compose.yaml up -d
docker compose --env-file infra/.env -f infra/compose.yaml ps
```

[로컬 Langfuse](http://localhost:3000)에 접속하세요. 로그인 이메일은 `demo@localhost.test`,
비밀번호는 `infra/.env`의 `LANGFUSE_INIT_USER_PASSWORD`입니다.
초기화 스크립트는 빈 `.env`의 Langfuse 키를 채웁니다. 기존 키가 있으면 유지합니다.
기존 Docker 볼륨이 있다면 초기화 값이 기존 계정을 다시 설정하지는 않습니다.

```powershell
python -m lab langfuse all --live
python -m lab langfuse query --live
```

실행별 안내와 중지 명령: [Langfuse 안내](docs/LANGFUSE.md).
SDK 5.0.4에는 서버 4.59.0 이상이 필요하며 제공 Compose는 4.68.0을 사용합니다.

## 4. LLaMA-Factory

학습은 **별도 Python 환경**에서 수행합니다. 큰 학습 의존성과 관찰 SDK의 충돌을 줄이기 위한 구성입니다.
Windows에서는 Linux/WSL2 + NVIDIA CUDA 환경을 권장하며 CPU 2-step 설정도 있습니다.

```powershell
python -m lab factory list
python -m lab factory run --recipe sft_lora
```

위 `run`은 실행 명령과 선행 조건만 보여줍니다. 학습 환경 설치 후 `--execute`를 붙이면
실제 모델 다운로드와 학습이 시작됩니다. 기본 모델은 공개된 `Qwen/Qwen2.5-0.5B-Instruct`입니다.

```text
python -m lab factory run --recipe sft_cpu --execute
python -m lab factory run --recipe sft_lora --execute
python -m lab factory run --recipe export --execute
python -m lab factory run --recipe api --execute
```

CPU와 GPU 학습은 선택지입니다. 둘 다 실행할 필요는 없습니다.
설치, 33개 설정, 선행 학습 순서, CPU 결과 연결 방법: [학습 실습 안내](factory/README.md).

## 5. 세 도구 연결

### 일반 채팅

Qwen과 자유롭게 대화하려면 다음 명령을 사용합니다. 최근 20턴의 대화를 기억하며,
`/exit`로 종료하고 `/reset`으로 새 대화를 시작합니다.

```powershell
python -m lab chat --live --stream
python -m lab chat --live --question "파이썬 리스트와 튜플의 차이는?"
# 서비스 실행 및 인증 설정 후 대화 기록:
python -m lab chat --live --stream --trace langfuse
python -m lab chat --live --stream --trace langsmith
python -m lab chat --live --stream --trace both
```

기본값은 로컬 기록만 사용합니다. `--trace`를 지정하면 질문·이전 대화·답변·토큰 사용량을
선택한 서비스에 전송합니다. 자세한 사용법과 Tool Calling/LangGraph 설명은
[일반 채팅 안내](docs/CHAT.md)를 참고하세요.
기존 `model chat`은 장애 분석 예제로 유지됩니다.

### 모델 서버 연결

ktcloud GPU 서버의 Qwen을 연결하려면 [ktcloud 연결 가이드](docs/KTCLOUD.md)를 참고하세요.
관찰 서비스 없이도 실제 모델 연결을 먼저 확인할 수 있습니다.

```powershell
python -m lab model models --live --save-model
python -m lab model chat --live
```

LLaMA-Factory의 `api` 또는 `api_base`를 별도 터미널에서 실행한 뒤,
관찰 도구용 `.venv`의 `.env`에 다음을 설정합니다.

```dotenv
LLM_BASE_URL=http://localhost:8000/v1
LLM_API_KEY=local-demo
LLM_MODEL=Qwen/Qwen2.5-0.5B-Instruct
```

서버가 다른 모델 이름을 반환하면 `/v1/models`의 ID로 `LLM_MODEL`을 변경하세요.
서버에서 API 인증을 켰다면 `LLM_API_KEY`도 일치시킵니다.

```powershell
python -m lab langsmith trace --live --model api
python -m lab langfuse trace --live --model api
python -m lab langsmith integrations --live --model api
python -m lab langfuse integrations --live --model api
python -m lab langsmith evaluate --live --model api
python -m lab langfuse evaluate --live --model api
```

`integrations`는 LangChain callback/추적과 실제 스트리밍을 보여줍니다.
엔드포인트가 `stream_options.include_usage`를 지원해야 토큰 수가 수집됩니다.
모델별 가격표가 없는 로컬 모델은 비용이 자동 계산되지 않을 수 있습니다.

`judge`는 실제 모델에 평가를 요청하는 선택 실습이며 `all`에 포함하지 않았습니다.
작은 모델은 평가 JSON을 정확히 출력하지 못할 수 있으므로 실패를 명시적으로 보고합니다.

```powershell
python -m lab langsmith judge --live --model api
python -m lab langfuse judge --live --model api
```

## 파일 찾기

```text
lab/                  공통 파이프라인과 두 도구 SDK 실행 예제
data/                 공통 지식 문서와 5개 평가 사례
factory/configs/      33개 YAML + DeepSpeed JSON
factory/data/         7개 등록 데이터셋과 합성 이미지
infra/                로컬 Langfuse Docker Compose
scripts/              설치 및 로컬 서버 초기화
tests/                로컬 동작과 실제 SDK 계약 검사
docs/                 도구별 안내·기능 점검표·검증 기록
artifacts/            실행 후 생성되는 결과 및 실습 ID
```

`all`을 다시 실행하면 새 실습 데이터셋·실험·검토 큐가 만들어지고 프롬프트 버전이 추가됩니다.
추적에는 의도한 오류가 하나 포함됩니다. 기존 원격 데이터를 삭제하지 않습니다.
`artifacts/*-state.json`은 후속 명령의 데이터셋/실행 ID를 연결합니다.
다른 서비스 프로젝트로 전환할 때는 해당 state 파일을 다른 이름으로 옮기고 `all`을 다시 실행하세요.

## 검증

```powershell
python -m pytest
ruff check lab scripts tests
python -m lab factory validate
```

현재 검증 범위와 실행하지 못한 항목은 [검증 기록](docs/VALIDATION.md)에 있습니다.
실제 서비스 수집 성공은 각 웹 화면에서도 확인해야 합니다. SDK가 전송 오류를 로그로만 남길 수 있습니다.

## 참고한 공식 자료

- [LangSmith 평가 SDK](https://docs.langchain.com/langsmith/evaluate-llm-application)
- [LangSmith Python API](https://reference.langchain.com/python/langsmith)
- [Langfuse Python SDK](https://langfuse.com/docs/observability/sdk/overview)
- [Langfuse 실험 실행](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)
- [Langfuse 로컬 배포](https://langfuse.com/self-hosting/deployment/docker-compose)
- [LLaMA-Factory v0.9.5](https://github.com/hiyouga/LLaMA-Factory/tree/v0.9.5)
- [LLaMA-Factory 데이터 형식](https://github.com/hiyouga/LLaMA-Factory/blob/v0.9.5/data/README.md)
