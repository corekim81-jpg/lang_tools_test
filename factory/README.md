# LLaMA-Factory 학습·추론 실습

기준 버전: **0.9.5**. 모든 경로는 프로젝트 루트 기준입니다.
YAML은 작은 데이터로 기능을 확인하는 smoke 실습 설정입니다. 성능 좋은 모델을 만들기 위한 학습량은 아닙니다.
학습/다운로드는 아직 실행하지 않았으며, 환경별 PyTorch/CUDA 및 메모리 조건을 먼저 맞춰야 합니다.

## 학습 환경 설치

Linux 또는 WSL2 터미널에서 저장소 루트로 이동한 뒤:

```bash
python3.11 -m venv .venv-llama
source .venv-llama/bin/activate
python -m pip install --upgrade pip
# 먼저 https://pytorch.org/get-started/locally/ 에서 현재 GPU/드라이버에 맞는 torch 설치
python -m pip install -r factory/requirements.txt
llamafactory-cli version
python -m lab factory validate
```

CPU도 지원하는 환경이지만 학습은 느립니다. Windows native에서 문제가 있으면 WSL2에서 별도 환경을 만드세요.
Windows의 `.venv`를 WSL에서 재사용하지 마세요. 이 환경에는 관찰 SDK를 설치할 필요가 없습니다.

선택 의존성은 해당 실습을 할 때만 설치합니다.

```bash
python -m pip install bitsandbytes      # sft_qlora; CUDA 지원 확인
python -m pip install galore-torch      # sft_galore
python -m pip install deepspeed         # Linux + 분산 학습
```

vLLM은 PyTorch 의존성 요구가 달라질 수 있어 별도 추론 환경을 권장합니다.
모델 다운로드에는 네트워크와 디스크 공간이 필요합니다. 0.5B 모델도 전체 학습 메모리는 가중치 파일 크기보다 큽니다.
정확한 VRAM 요구량은 정밀도, optimizer, sequence length, batch size에 따라 달라집니다.

## 첫 실행

```bash
python -m lab factory run --recipe sft_lora           # 명령 미리보기
python -m lab factory run --recipe sft_lora --execute # 실제 GPU 학습
```

CPU만 사용한다면 GPU 명령 대신:

```bash
python -m lab factory run --recipe sft_cpu --execute
```

학습 결과는 각각 `saves/sft_lora`, `saves/sft_cpu`입니다.
loss 로그, adapter_config.json, adapter 가중치, checkpoint 폴더가 생기는지 확인합니다.
기본 GPU 설정은 4 step, CPU는 2 step입니다. 설정을 수정할 때 `output_dir`도 새 경로로 지정하세요.
실행기는 비어 있지 않은 결과 폴더의 덮어쓰기를 막습니다. `resume`은 예외입니다.

## 33개 설정

`python -m lab factory run --recipe <이름> --execute`로 실행합니다.

| 이름 | 목적 | 추가 조건/결과 |
|---|---|---|
| sft_lora | 지도 미세조정, LoRA | GPU 기본 예제 |
| sft_cpu | CPU 미세조정 | fp16=false, 2 step |
| pt_lora | continued pretraining | base 모델, 일반 텍스트 |
| sft_full | 전체 파라미터 학습 | 더 큰 메모리 |
| sft_freeze | 마지막 레이어 학습 | freeze_trainable_layers=1 |
| sft_qlora | 4-bit QLoRA | bitsandbytes/CUDA |
| rm_lora | reward model | chosen/rejected 쌍, value head |
| ppo_lora | PPO | sft_lora + rm_lora 선행 |
| dpo_lora | DPO | pref_loss=sigmoid |
| orpo_lora | ORPO | stage=dpo, pref_loss=orpo |
| simpo_lora | SimPO | stage=dpo, pref_loss=simpo |
| kto_lora | KTO | true/false 선호 라벨 |
| sft_dora | DoRA | use_dora |
| sft_rslora | rsLoRA | use_rslora |
| sft_pissa | PiSSA | 초기화, pissa_iter=4 |
| sft_loraplus | LoRA+ | 학습률 비율 |
| sft_oft | OFT | OFT 호환 PEFT |
| sft_galore | GaLore | galore-torch, full tuning |
| sft_tensorboard | 학습 시각화 | tensorboard --logdir saves |
| sft_packing | 샘플 packing | 짧은 데이터 묶기 |
| preprocess | tokenized dataset 캐시 | artifacts/tokenized; 저장 후 종료 |
| resume | 체크포인트 재개 | sft_lora/checkpoint-2 선행 |
| eval_loss | 별도 검증 데이터 loss | sft_lora 선행 |
| predict | 생성 답변 평가/저장 | sft_lora 선행 |
| multimodal | 이미지+텍스트 SFT | Qwen2-VL-2B, 더 큰 GPU 메모리 |
| sft_ddp | DDP | GPU 2개, torchrun |
| sft_deepspeed | ZeRO-2 | Linux, GPU 2개, DeepSpeed |
| chat_base | 기본 모델 대화 | 학습 없이 가능 |
| chat | adapter 대화 | sft_lora 선행 |
| api_base | 기본 모델 HTTP API | 학습 없이 가능 |
| api | adapter HTTP API | sft_lora 선행 |
| api_vllm | vLLM 서버 | export 선행, vLLM 환경 |
| export | LoRA 병합 | sft_lora → saves/merged |

별도 `webui` 명령도 있습니다: `python -m lab factory run --recipe webui --execute`.
LLaMA Board에서 모델, 데이터 경로, 학습 방법을 지정하고 명령 미리보기를 YAML과 비교합니다.

## 실행 순서

```text
sft_lora ─┬─→ chat / api / eval_loss / predict
          ├─→ export → api_vllm
          └─→ checkpoint-2 → resume
sft_lora + rm_lora → ppo_lora
나머지 학습 설정은 독립 실행 가능
```

CPU 학습 결과를 사용하려면 chat/api/export/eval_loss/predict YAML의
`adapter_name_or_path`를 `saves/sft_cpu`로 수정하세요.
CPU에서 eval_loss/predict를 실행하려면 해당 YAML에 `use_cpu: true`, `fp16: false`도 설정합니다.
실행기는 수정한 YAML의 adapter 경로를 읽어 선행 조건을 확인합니다.

## 데이터 살펴보기

- train.json: 4종 장애 × 3질문, Alpaca instruction/input/output.
- eval.json: 학습 질문과 다른 검증 질문 5개. 도메인은 공유하므로 일반화 평가용 벤치마크는 아닙니다.
- pairs.json: RM/DPO/ORPO/SimPO용 chosen/rejected. 부적절한 답변도 학습 형식 설명용 합성 문장입니다.
- kto.json: ShareGPT conversations + kto_tag boolean.
- text.json: continued pretraining용 일반 텍스트.
- prompts.json: PPO용 질문.
- images.json + status.png: 이미지 토큰과 경로를 포함한 합성 멀티모달 데이터.
- dataset_info.json: 데이터 이름, 파일, 열 매핑 등록.

`prepare`는 기존 파일을 유지합니다. 직접 수정한 생성 파일을 초기화할 때만 `prepare --force`를 사용하세요.
이미지/대화 데이터는 `dataset_dir` 기준으로 경로를 해석합니다.

## 평가·추론

```bash
python -m lab factory run --recipe eval_loss --execute
python -m lab factory run --recipe predict --execute
python -m lab factory run --recipe export --execute
python -m lab factory run --recipe api --execute
```

기본 API 포트는 8000입니다. 별도 터미널에서 `/v1/models`와 `/v1/chat/completions`를 확인합니다.
루트 README의 `--model api` 예제와 연결하면 LangSmith/Langfuse에서 동일 모델을 평가합니다.
LoRA 병합 시 quantization_bit 설정은 사용하지 않습니다.

## 분산 학습과 로그

```bash
export CUDA_VISIBLE_DEVICES=0,1
python -m lab factory run --recipe sft_ddp --execute
python -m lab factory run --recipe sft_deepspeed --execute
tensorboard --logdir saves
```

실행기가 두 분산 recipe에 FORCE_TORCHRUN=1과 기본 NPROC_PER_NODE=2를 설정합니다.
W&B/MLflow/SwanLab 같은 외부 logger는 해당 패키지와 계정을 준비한 뒤
YAML의 report_to를 변경해 실습할 수 있습니다. 여기서는 TensorBoard를 실행 예제로 제공합니다.

## 확장 범위

추가 모델, 음성·영상, 도구 호출 데이터, FlashAttention/Unsloth, 다른 양자화 backend,
APOLLO/BAdam, Megatron 및 benchmark별 평가는 환경별 선택 기능입니다.
[공식 examples](https://github.com/hiyouga/LLaMA-Factory/tree/v0.9.5/examples)를 참고해
이 프로젝트의 데이터/출력 경로를 유지하며 별도 설정을 추가하세요.
이러한 조합은 현재 33개 설정의 검증 범위에 포함되지 않습니다.
