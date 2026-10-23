# 검증 기록

확인일: 2026-10-23, Windows / Python 3.12.6.

## 확인한 결과

| 검사 | 결과 |
|---|---|
| 로컬 offline 실습 | baseline/good 평가 보고서 생성 |
| pytest | **23 passed** |
| Ruff | All checks passed |
| LLaMA-Factory 데이터 형식·설정 정적 검사 | **7개 데이터셋 / 33개 YAML 통과** |
| Docker Compose config --quiet | 통과; 서버 시작 없이 구문·변수 해석 검사 |
| uv sync --frozen --offline | 고정 버전 설치 상태 확인 |
| factory run 미리보기 | 학습 실행 없이 명령·선행 결과 경로 출력 확인 |

테스트는 다음을 검증합니다.

- 5개 합성 사례의 검색·응답·점수 및 알 수 없는 질문 처리.
- offline 모드에서 모델 클라이언트를 만들지 않음.
- 재귀 마스킹과 **실제 Langfuse SDK가 내보내는 데이터의 마스킹 결과**.
- 실제 LangSmith SDK의 로컬 부모·자식 run 구조.
- 실제 Langfuse SDK와 메모리 exporter를 통한 observation 구조.
- 실제 모델 SDK와 모의 HTTP 응답을 사용한 응답 처리.
- LangSmith/Langfuse 모델 wrapper의 스트리밍·토큰 usage 수집.
- 평가 함수 형식, JSON 평가자의 잘못된 응답 거부.
- 학습/검증 질문 분리, 선호 데이터 형식, PNG 구조.
- 설정 생성 시 사용자 수정 보존, 실행 전 선행 결과 누락 처리.

LangSmith 패키지 내부에서 deprecation warning 2개가 발생했습니다.
테스트 실패는 없으며 해당 패키지의 향후 업그레이드 시 다시 확인할 항목입니다.

## 아직 실행하지 않은 항목

| 항목 | 이유 / 다음 실행 조건 |
|---|---|
| LangSmith 실제 클라우드 수집·프롬프트·실험·큐 생성 | LANGSMITH_API_KEY 미설정; 계정 키 설정 후 `langsmith all --live` |
| Langfuse 실제 서버 수집·웹 화면 | Docker Desktop Linux 엔진 꺼짐; 엔진 시작 후 Compose up 및 `langfuse all --live` |
| 외부/로컬 실제 모델 호출 | 실제 모델 서버를 시작하지 않음; mock HTTP로 SDK 계약만 검사 |
| LLaMA-Factory 학습/다운로드/병합/추론 | 별도 학습 환경 미설치, nvidia-smi 없음; factory/README.md 참조 |
| 분산·양자화·멀티모달 학습 | 해당 하드웨어/선택 의존성 필요 |
| UI·기업용·관리자 기능 | 실제 프로젝트·관리자 권한·요금제별 확인 필요 |

이 검증은 클라우드나 GPU 학습의 end-to-end 성공을 보증하지 않습니다.
모든 코드/설정/수동 실습의 범위는 FEATURE_MATRIX.md에서 확인할 수 있습니다.

## 고정 버전

- langsmith 0.14.12
- langfuse 5.0.4
- langchain-core 1.7.0
- openai 3.37.0 (호환 API 클라이언트)
- LLaMA-Factory 0.9.5 (별도 설치 대상)
- Langfuse 서버 이미지 4.68.0 (Compose 대상)

관찰 도구의 전체 의존성은 uv.lock으로 고정했습니다.
학습 전용 requirements는 LLaMA-Factory 버전을 고정하며, PyTorch/CUDA와 선택 가속 라이브러리는
실행할 장비에 맞게 설치해야 합니다. 학습 환경 전체를 잠근 파일은 아닙니다.
