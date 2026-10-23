# ktcloud GPU 서버의 Qwen 연결

이 프로젝트는 OpenAI 호환 `/v1/models`, `/v1/chat/completions` 서버를 사용할 수 있습니다.
모델은 ktcloud GPU에서 실행하고, 현재 PC에서는 질문 전송·평가·추적을 수행합니다.
원격 추론 API를 연결하는 것만으로 LLaMA-Factory 학습이 원격에서 실행되는 것은 아닙니다.

## 이번 주소에서 확인한 사항

- 사용자가 제공한 `*.proxy3.ainexus.ktcloud.com/v1/models`에 일반 HTTP 요청을 보냈을 때
  **401 `Not Authenticated - INVALIDCOOKIE`** 응답을 받았습니다.
- 브라우저가 열리는 것과 Python API 접근은 다릅니다. 이 응답은 프록시의 브라우저 세션 인증이
  필요한 상태임을 나타냅니다. Python SDK는 브라우저 로그인 세션을 자동으로 가져오지 않습니다.
- 2026-10-23 새로 받은 `C:\Users\yjkim\.ssh\id_container`로 `bai-vscode` SSH 접속에 성공했습니다.
- 서버의 vLLM 수신 포트는 **8000**, `/v1/models`가 반환한 모델 ID는 **`qwen3.8-27b`**입니다.
- PC의 **`http://127.0.0.1:18000/v1`**로 SSH 터널을 연결하고 `.env`에 저장했습니다.
- 일반 대화, 스트리밍 대화, 기존 장애 분석 파이프라인의 실제 Qwen 응답을 확인했습니다.
  응답과 토큰 사용량은 `artifacts/model-report.json`, 파이프라인 응답은
  `artifacts/model-pipeline-report.json`에서 확인할 수 있습니다. 실행할 때 보고서는 덮어씁니다.
- 현재 터널은 백그라운드로 실행됩니다. PC 재시작이나 SSH 연결 종료 후에는 아래 명령으로 다시 연결하세요.

## 방법 A: API용 주소와 인증이 따로 있는 경우

서버 관리자 또는 ktcloud 배포 설정에서 **프로그램용 API endpoint와 인증 방식**을 확인합니다.
브라우저 로그인 주소만으로 API key 방식도 지원한다고 가정하지 마세요.

`.env`에서 모델 연결 항목을 수정합니다. 기존 LangSmith/Langfuse 항목은 유지하세요.

```dotenv
LLM_BASE_URL=https://<프로그램용-모델-주소>/v1
LLM_API_KEY=<해당-API의-키>
LLM_TIMEOUT=120
```

`LLM_BASE_URL`은 `/v1`까지만 적습니다. `/v1/models`나 `/v1/chat/completions`를 붙이지 않습니다.
현재 클라이언트는 Bearer API 키 방식입니다. 별도 프록시 인증 헤더가 필요한 환경이면
그 환경이 제공하는 공식 인증 방식에 맞게 추가 설정해야 합니다.

## 방법 B: 기존 SSH 권한으로 포트 전달

브라우저용 프록시 대신 **인증된 SSH 연결 안에서** 모델 서버의 포트를 전달할 수 있습니다.
서버의 공개 설정이나 인증 정책은 바꾸지 않습니다.

1. SSH 별칭 `bai-vscode`와 개인 키 `~/.ssh/id_container`를 준비합니다.
   이 서버는 `ss` 명령이 없어 수신 포트와 vLLM 실행 인자를 통해 **8000**을 확인했습니다.
   서버 안에서는 `curl http://127.0.0.1:8000/v1/models`로도 확인할 수 있습니다.
   모델 API 자체 인증이 있으면 그 키도 필요합니다.
   다른 컨테이너에서 실행된다면 SSH로 접속한 환경의 localhost에서 접근 가능한 매핑 포트를 사용해야 합니다.

2. PC의 PowerShell에서 터널을 시작합니다. 현재 터널이 실행 중이면 다시 시작할 필요가 없습니다.

   ```powershell
   cd D:\AI\src\lang_tools_test
   powershell -ExecutionPolicy Bypass -File scripts/start-model-tunnel.ps1 -RemotePort 8000 -Background
   ```

   SSH 별칭 기본값은 `bai-vscode`, 로컬 포트는 18000입니다.
   다른 별칭/포트는 `-SshHost 이름 -LocalPort 포트`, 다른 개인 키는 `-IdentityFile 경로`로 지정합니다.
   키의 내용은 코드나 `.env`에 복사하지 않습니다.

   새 PC의 최초 연결은 `-Background`를 빼고 실행해 서버 호스트 키를 확인하세요.
   호스트 기록은 프로젝트의 `.cache/ktcloud_known_hosts`에 저장되며, 이후 백그라운드 연결은
   이 기록과 일치하는 호스트만 허용합니다. 최초 연결 창은 Ctrl+C로 종료한 뒤 백그라운드로 시작할 수 있습니다.
   암호문구가 있는 개인 키는 SSH 에이전트에 로드하거나 전경 모드에서 직접 입력하세요.

   백그라운드 터널 종료:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/stop-model-tunnel.ps1
   ```

   종료 스크립트는 저장된 프로세스가 해당 SSH 포트 전달인지 확인합니다.
   전경 모드는 실행 창을 켜 두고 Ctrl+C로 종료합니다.
   SSH 오류는 `.cache/model-tunnel.stderr.log`에서 확인합니다.

3. `.env`에서 모델 주소를 로컬 터널로 설정합니다.

   ```dotenv
   LLM_BASE_URL=http://127.0.0.1:18000/v1
   LLM_API_KEY=local-demo
   LLM_MODEL=qwen3.8-27b
   LLM_TIMEOUT=120
   LLM_MAX_TOKENS=2048
   LAB_MODEL_MODE=api
   ```

   `local-demo`는 **모델 서버 자체에 API 키 인증이 없을 때만** 사용하는 SDK용 자리표시자입니다.
   SSH 인증을 대신하는 키가 아닙니다. 모델 서버가 키를 요구하면 실제 키를 입력해야 합니다.

   이 모델의 첫 검증 응답은 출력 383토큰 중 추론에 322토큰을 사용했습니다.
   `LLM_MAX_TOKENS`는 추론과 답변을 포함하는 한도이므로 기존 256토큰으로는 부족할 수 있습니다.
   현재 값 2048은 모든 실제 생성·평가자·스트리밍 호출에 적용됩니다.
   복잡한 질문에서 `length`가 반환되면 더 늘리세요. 생성·평가자는 잘린 답변을 성공으로 처리하지 않습니다.

   개인 키, `.env`, `.cache`, 실행 보고서는 Git에 업로드하지 않습니다.

## 실제 모델 이름 확인과 대화

활성화한 `.venv`에서:

```powershell
python -m lab model models --live
python -m lab model models --live --save-model
python -m lab model chat --live
python -m lab model chat --live --stream
```

`--save-model`은 서버에 모델이 하나일 때만 그 정확한 ID를 `.env`의 `LLM_MODEL`에 저장합니다.
여러 모델이면 목록에서 하나를 골라 직접 설정합니다. Qwen이라는 이름만으로 버전이나 모델 ID를 추정하지 않습니다.
실제 채팅 성공 시 `artifacts/model-report.json`에 응답·소요 시간·반환된 토큰 사용량이 저장됩니다.
이 명령은 LangSmith/Langfuse 서버가 없어도 실행됩니다.

## LangSmith/Langfuse 연결

위 대화가 성공하면 관찰 도구에 같은 모델을 연결합니다.

```powershell
python -m lab langfuse trace --live --model api
python -m lab langfuse evaluate --live --model api
python -m lab langsmith trace --live --model api
python -m lab langsmith evaluate --live --model api
```

각 서비스의 URL/키도 별도로 설정되어 있어야 합니다. 모델 API 키와 관찰 서비스 키는 서로 다릅니다.
매번 `--model api`를 쓰지 않으려면 연결 성공 후 `.env`에 `LAB_MODEL_MODE=api`를 설정합니다.
`offline` 명령은 이 값과 무관하게 로컬 규칙 실습으로 유지됩니다.

## 오류별 확인

| 오류 | 확인 사항 |
|---|---|
| 401 INVALIDCOOKIE | 브라우저 세션 전용 프록시인지 확인; API용 접속 또는 SSH 터널 사용 |
| 401/403 | 모델 서버와 프록시가 요구하는 인증 구분 |
| Permission denied (publickey,password) | id_container가 현재 컨테이너용 키인지 확인; -IdentityFile 경로 지정 |
| Host key verification failed | 서버 재생성 여부와 새 호스트 키를 확인; 검증을 끄지 말고 신뢰할 수 있는 경로로 갱신 |
| managed tunnel record exists / port already in use | 기존 터널이면 그대로 사용; 재연결은 stop 후 start |
| Connection refused | 터널 창, 원격 수신 포트, 모델 실행 상태 확인 |
| 404 | base URL이 `/v1`까지인지, chat/completions 제공 여부 확인 |
| model not found | models가 반환한 정확한 ID 사용 |
| 빈 답변 또는 length | LLM_MAX_TOKENS를 늘리고 Qwen 모델의 thinking/chat template 확인 |
| stream_options 오류 | 서버의 스트리밍 usage 지원 확인; 일반 chat으로 먼저 검증 |

`.env`를 바꿔도 같은 이름의 PowerShell 환경 변수가 이미 설정되어 있으면 환경 변수가 우선합니다.
필요한 변수만 해당 터미널에서 해제하거나 새 터미널에서 다시 실행하세요.
