# 기능 점검표와 제공 범위

2026-10-23에 확인한 공식 문서와 설치된 SDK 기준입니다.
**코드**는 실행 예제가 있음, **설정**은 학습/서버 설정이 있음, **수동**은 UI 실습 절차가 있음,
**확장**은 별도 구현·환경 구성이 필요함을 뜻합니다. 코드/설정이 있다는 것이 원격 실행 검증을 의미하지는 않습니다.

## LangSmith

| 기능 | 제공 형태 | 실행 또는 확인 경로 |
|---|---|---|
| 함수·계층 추적, 입력/출력, RAG | 코드 | trace |
| 실패·예외 추적 | 코드 | trace의 intentional-error |
| metadata, tags, 사용자·세션 | 코드 | trace의 root metadata |
| async/context 전파 | 코드 | async |
| 데이터 마스킹 | 코드 | Client hide_inputs/hide_outputs |
| LangChain 연동 | 코드 | integrations |
| 모델 SDK 자동 추적·토큰·stream | 코드 | trace --model api / integrations |
| private prompt 저장·버전·조회 | 코드 | prompts |
| 프롬프트 Playground·태그 승격 | 수동 | LANGSMITH.md |
| 데이터셋·사례·split·버전 태그 | 코드 | dataset |
| 데이터 수정·버전 비교 | 수동 | LANGSMITH.md |
| 실험, custom/summary evaluator | 코드 | evaluate |
| 동시 실행·실험 메타데이터 | 코드 | evaluate |
| A/B, pairwise 평가 | 코드 | compare |
| LLM-as-a-judge | 코드 | judge --model api |
| 피드백·사람 검토 큐 | 코드+수동 | feedback 및 생성된 큐 |
| 실행 필터·조회·내보내기 | 코드 | query; 현재 최대 20개 |
| 온라인 평가·자동화 규칙 | 수동 | lab trace 전용 규칙 생성 → 새 trace 점수 확인 |
| 비용·성능 대시보드 | 수동 | 실제 usage/모델 가격이 있는 trace로 확인 |
| 배포·Studio·Agent Server | 확장 | 별도의 배포 가능한 에이전트 앱과 배포 대상이 필요 |
| Gateway, 중앙 키·한도 관리 | 확장 | 계정 제공 여부 확인 후 테스트 모델 연결/한도 요청 검사 |
| SSO/RBAC/감사·보관·셀프호스팅 | 수동/확장 | 테스트 조직·관리자 권한·제품 제공 범위가 필요 |
| distributed HTTP propagation, 다른 언어 SDK | 확장 | 단일 Python 프로세스 예제를 별도 서비스로 분리해야 함 |

## Langfuse

| 기능 | 제공 형태 | 실행 또는 확인 경로 |
|---|---|---|
| span/agent/retriever/generation/tool | 코드 | trace |
| context manager / 수동 end | 코드 | trace |
| observe decorator / async | 코드 | async |
| 사용자·세션·환경·태그 | 코드 | trace, environment=lab |
| 오류와 마스킹 | 코드 | trace / Langfuse(mask=...) |
| 모델 SDK / LangChain / streaming | 코드 | integrations --model api |
| 토큰 usage·비용 | 코드+수동 | API 응답 usage와 모델 가격 매핑 |
| text/chat prompt, compile, 버전 | 코드 | prompts |
| 라벨·캐시·generation 연결 | 코드 | prompts |
| prompt 롤백 / Playground | 수동 | LANGFUSE.md |
| 데이터셋·항목·안정 ID | 코드 | dataset |
| 데이터 버전/변경 이력 | 수동 | 시각을 지정한 get_dataset 확인 |
| hosted experiment / custom·집계 점수 | 코드 | evaluate |
| 실험 비교 | 코드+수동 | baseline/good 생성 후 UI에서 비교 |
| numeric/boolean/category/session 점수 | 코드 | scores |
| LLM-as-a-judge | 코드 | judge --model api |
| 온라인 평가·annotation | 수동 | LANGFUSE.md |
| 미디어 observation | 코드 | media; 합성 PNG |
| Observations API v2 | 코드 | query; 현재 최대 50개 |
| self-host Docker Compose | 설정 | infra/compose.yaml |
| sampling | 설정 | Langfuse(sample_rate=1.0)를 0~1로 변경 후 trace 개수 비교 |
| 대시보드·custom model pricing | 수동 | LANGFUSE.md |
| OTel 다른 서비스/SDK 연동 | 확장 | 현재는 Python SDK의 OTel export만 테스트 |
| bulk export / retention / RBAC / SSO | 수동/확장 | 테스트 프로젝트의 기능 제공 여부·권한 확인 필요 |
| Halo 등 인앱 AI 기능 | 확장 | 서버/계정의 별도 모델 연결과 해당 기능 설정 필요 |

## LLaMA-Factory

| 기능군 | 제공 형태 | 설정/자료 |
|---|---|---|
| PT/SFT/RM/PPO/DPO/KTO/ORPO/SimPO | 설정 | factory/configs의 해당 recipe |
| LoRA/QLoRA/Full/Freeze/OFT | 설정 | sft_* |
| DoRA/rsLoRA/PiSSA/LoRA+ | 설정 | sft_dora/rslora/pissa/loraplus |
| GaLore | 설정 | sft_galore |
| Alpaca/ShareGPT/선호/이진 라벨 | 데이터+검사 | factory/data 및 validate |
| 이미지+텍스트 | 설정+데이터 | multimodal, status.png |
| packing / token cache | 설정 | sft_packing / preprocess |
| CPU / GPU / mixed precision | 설정 | sft_cpu / sft_lora |
| DDP / DeepSpeed ZeRO-2 | 설정 | sft_ddp / sft_deepspeed |
| checkpoint / resume | 설정 | sft_lora checkpoint-2 / resume |
| loss 평가 / 생성 답변 저장 | 설정 | eval_loss / predict |
| loss plot / TensorBoard | 설정 | plot_loss / sft_tensorboard |
| LoRA 병합 / export | 설정 | export |
| 채팅 / API / vLLM | 설정 | chat / api / api_vllm |
| LLaMA Board | 실행 경로 | factory run --recipe webui --execute |
| 다양한 모델/양자화 backend | 확장 | 모델·template·데이터 호환성을 확인해 새 YAML 추가 |
| 음성·영상·도구 호출 데이터 | 확장 | 공식 데이터 형식에 맞는 별도 fixture 필요 |
| FlashAttention/Unsloth/APOLLO/BAdam | 확장 | 해당 환경·의존성·호환 조합 추가 필요 |
| Megatron, 다중 노드, 기타 가속기 | 확장 | 전용 클러스터/장비와 launch 설정 필요 |
| W&B/MLflow/SwanLab | 수동 설정 | 패키지·계정 준비 후 report_to 변경 |
| MMLU 등 정식 벤치마크 | 확장 | 전용 데이터/평가 설정 필요; 제공 검증 세트는 합성 smoke test |

## 전체 제품 기능을 점검할 때의 추가 절차

1. 사용할 제품 버전/요금제와 테스트 조직을 고정합니다.
2. 코드/설정 항목을 먼저 실행하고 UI에서 결과를 확인합니다.
3. 관리자 기능은 테스트 계정 두 개로 역할별 읽기/쓰기 차이를 확인합니다.
4. 온라인 평가에는 lab 환경 필터를 걸고 새로운 실행 한 개로 규칙 작동을 확인합니다.
5. 배포/Gateway는 별도 테스트 endpoint를 만들고 요청 성공·실패·usage를 확인합니다.
6. 확장 학습 기능은 기본 sft_lora 성공 후 한 번에 한 설정만 변경합니다.

기업 기능과 클러스터 조합까지 이 폴더의 `all` 하나로 테스트하는 것은 지원 범위가 아닙니다.
`all`은 CLI의 기본 SDK 실습 묶음이며, 확장 항목을 자동 실행하지 않습니다.
