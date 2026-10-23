"""Generate small, inspectable LLaMA-Factory v0.9.5 recipes and validate their dependencies."""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import zlib
from copy import deepcopy
from pathlib import Path

import yaml

from lab.common import ROOT, answer, cases, read_json

FACTORY = ROOT / "factory"
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


def recipes() -> dict[str, dict]:
    base = {
        "model_name_or_path": MODEL,
        "trust_remote_code": False,
        "stage": "sft",
        "do_train": True,
        "finetuning_type": "lora",
        "lora_rank": 8,
        "lora_target": "all",
        "template": "qwen",
        "dataset_dir": "factory/data",
        "dataset": "incident_train",
        "cutoff_len": 256,
        "max_samples": 16,
        "preprocessing_num_workers": 1,
        "dataloader_num_workers": 0,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 2,
        "max_steps": 4,
        "learning_rate": 1e-4,
        "lr_scheduler_type": "cosine",
        "logging_steps": 1,
        "save_steps": 2,
        "save_total_limit": 2,
        "plot_loss": True,
        "report_to": "none",
        "fp16": True,
        "seed": 42,
        "overwrite_output_dir": False,
    }
    result = {}

    def add(name, description, *, command="train", requires=(), **updates):
        config = (
            deepcopy(base)
            if command == "train"
            else {
                "model_name_or_path": MODEL,
                "template": "qwen",
                "trust_remote_code": False,
            }
        )
        if command == "train":
            config["output_dir"] = f"saves/{name}"
        config.update(updates)
        if config.get("finetuning_type") not in (None, "lora"):
            config.pop("lora_rank", None)
            config.pop("lora_target", None)
        result[name] = {
            "description": description,
            "command": command,
            "requires": list(requires),
            "config": config,
        }

    add("sft_lora", "지도 미세조정 + LoRA; 기본 GPU 실습")
    add(
        "sft_cpu",
        "CPU 전용 2-step 학습; 느리지만 GPU 없이 가능",
        use_cpu=True,
        fp16=False,
        max_steps=2,
        cutoff_len=128,
        gradient_accumulation_steps=1,
    )
    add(
        "pt_lora",
        "일반 텍스트로 continued pretraining",
        stage="pt",
        model_name_or_path="Qwen/Qwen2.5-0.5B",
        dataset="incident_text",
    )
    add("sft_full", "전체 파라미터 학습", finetuning_type="full", learning_rate=1e-5)
    add("sft_freeze", "마지막 레이어만 학습", finetuning_type="freeze", freeze_trainable_layers=1)
    add(
        "sft_qlora",
        "4-bit bitsandbytes QLoRA; CUDA 환경 권장",
        quantization_bit=4,
        quantization_method="bnb",
    )
    add("rm_lora", "선호/비선호 쌍으로 reward model 학습", stage="rm", dataset="incident_pairs")
    add(
        "ppo_lora",
        "SFT adapter + reward model로 PPO",
        stage="ppo",
        dataset="incident_prompts",
        adapter_name_or_path="saves/sft_lora",
        reward_model="saves/rm_lora",
        reward_model_type="lora",
        requires=("saves/sft_lora/adapter_config.json", "saves/rm_lora/adapter_config.json"),
    )
    for name, loss in (("dpo_lora", "sigmoid"), ("orpo_lora", "orpo"), ("simpo_lora", "simpo")):
        add(
            name,
            f"선호 최적화 ({loss})",
            stage="dpo",
            dataset="incident_pairs",
            pref_loss=loss,
            pref_beta=0.1,
        )
    add("kto_lora", "좋음/나쁨 이진 라벨로 KTO", stage="kto", dataset="incident_kto", pref_beta=0.1)
    add("sft_dora", "DoRA adapter", use_dora=True)
    add("sft_rslora", "Rank-stabilized LoRA", use_rslora=True)
    add("sft_pissa", "PiSSA 초기화", pissa_init=True, pissa_iter=4)
    add("sft_loraplus", "LoRA+ 학습률 비율", loraplus_lr_ratio=16.0)
    add("sft_oft", "OFT adapter; 호환 PEFT 필요", finetuning_type="oft", oft_target="all")
    add(
        "sft_galore",
        "GaLore optimizer; galore-torch 추가 설치 필요",
        finetuning_type="full",
        use_galore=True,
        galore_rank=16,
    )
    add("sft_tensorboard", "학습 로그를 TensorBoard로 확인", report_to="tensorboard")
    add("sft_packing", "짧은 샘플 packing", packing=True)
    add("preprocess", "tokenized dataset 저장 후 종료", tokenized_path="artifacts/tokenized")
    add(
        "resume",
        "2-step checkpoint부터 재개",
        output_dir="saves/sft_lora",
        resume_from_checkpoint="saves/sft_lora/checkpoint-2",
        requires=("saves/sft_lora/checkpoint-2/trainer_state.json",),
    )
    add(
        "eval_loss",
        "별도 검증 세트 loss 평가",
        do_train=False,
        do_eval=True,
        eval_dataset="incident_eval",
        adapter_name_or_path="saves/sft_lora",
        per_device_eval_batch_size=1,
        requires=("saves/sft_lora/adapter_config.json",),
    )
    add(
        "predict",
        "검증 세트 생성 응답 저장",
        do_train=False,
        do_predict=True,
        predict_with_generate=True,
        eval_dataset="incident_eval",
        adapter_name_or_path="saves/sft_lora",
        per_device_eval_batch_size=1,
        max_new_tokens=128,
        requires=("saves/sft_lora/adapter_config.json",),
    )
    add(
        "multimodal",
        "합성 상태 이미지 + 텍스트 SFT; 큰 GPU 메모리 필요",
        model_name_or_path="Qwen/Qwen2-VL-2B-Instruct",
        template="qwen2_vl",
        dataset="incident_images",
        image_max_pixels=12544,
        cutoff_len=512,
    )
    add("sft_ddp", "2 GPU DDP; CUDA_VISIBLE_DEVICES와 NPROC_PER_NODE 설정 필요")
    add(
        "sft_deepspeed",
        "DeepSpeed ZeRO-2; Linux/다중 GPU/추가 설치 필요",
        deepspeed="factory/configs/deepspeed_zero2.json",
    )
    for name, command, config in (
        ("chat_base", "chat", {}),
        ("chat", "chat", {"adapter_name_or_path": "saves/sft_lora"}),
        ("api_base", "api", {}),
        ("api", "api", {"adapter_name_or_path": "saves/sft_lora"}),
        ("api_vllm", "api", {"model_name_or_path": "saves/merged", "infer_backend": "vllm"}),
        (
            "export",
            "export",
            {
                "adapter_name_or_path": "saves/sft_lora",
                "export_dir": "saves/merged",
                "export_size": 2,
                "export_device": "cpu",
                "export_legacy_format": False,
            },
        ),
    ):
        requires = (
            ("saves/sft_lora/adapter_config.json",) if "adapter_name_or_path" in config else ()
        )
        if name == "api_vllm":
            requires = ("saves/merged/config.json",)
        add(name, f"{command}: {name}", command=command, requires=requires, **config)
    return result


def status_png() -> bytes:
    """A self-generated 112x112 red/green status fixture, no external image dependency."""
    width = height = 112
    raw = b"".join(
        b"\0" + b"".join(bytes((220, 40, 40) if x < 56 else (30, 170, 90)) for x in range(width))
        for _ in range(height)
    )

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def prepare(force=False):
    folder = FACTORY / "data"
    configs = FACTORY / "configs"
    folder.mkdir(parents=True, exist_ok=True)
    configs.mkdir(parents=True, exist_ok=True)

    def write(path: Path, value):
        if path.exists() and not force:
            return
        if isinstance(value, bytes):
            path.write_bytes(value)
        else:
            path.write_text(value, encoding="utf-8")

    def write_json(path, data):
        write(path, json.dumps(data, ensure_ascii=False, indent=2))

    knowledge = read_json(ROOT / "data" / "knowledge.json")
    train = []
    for doc in knowledge:
        for question in (
            f"{doc['keywords'][0]} 장애 원인과 조치를 설명하세요.",
            f"{doc['keywords'][0]} 관련 경고가 발생했습니다. 점검 방법은?",
            f"{doc['keywords'][0]} 문제 대응 보고서를 작성해 주세요.",
        ):
            train.append(
                {
                    "instruction": question,
                    "input": "",
                    "output": answer({"question": question})["answer"],
                }
            )
    evaluation = [
        {
            "instruction": c["inputs"]["question"],
            "input": "",
            "output": answer(c["inputs"])["answer"],
        }
        for c in cases()
    ]
    pairs = [
        {
            "instruction": row["instruction"],
            "chosen": row["output"],
            "rejected": "근거는 없지만 모든 서버를 즉시 삭제하세요.",
        }
        for row in train
    ]
    kto = []
    for row in pairs:
        for key, good in (("chosen", True), ("rejected", False)):
            kto.append(
                {
                    "conversations": [
                        {"from": "human", "value": row["instruction"]},
                        {"from": "gpt", "value": row[key]},
                    ],
                    "kto_tag": good,
                }
            )
    write_json(folder / "train.json", train)
    write_json(folder / "eval.json", evaluation)
    write_json(folder / "pairs.json", pairs)
    write_json(folder / "kto.json", kto)
    write_json(folder / "text.json", [{"text": d["text"]} for d in knowledge])
    write_json(
        folder / "prompts.json", [{"instruction": r["instruction"], "output": ""} for r in train]
    )
    write(folder / "status.png", status_png())
    write_json(
        folder / "images.json",
        [
            {
                "conversations": [
                    {"from": "human", "value": "<image>상태 패널의 두 색을 설명하세요."},
                    {"from": "gpt", "value": "왼쪽은 빨간색, 오른쪽은 초록색입니다."},
                ],
                "images": ["status.png"],
            }
        ]
        * 4,
    )
    write_json(
        folder / "dataset_info.json",
        {
            "incident_train": {"file_name": "train.json"},
            "incident_eval": {"file_name": "eval.json"},
            "incident_text": {"file_name": "text.json", "columns": {"prompt": "text"}},
            "incident_prompts": {"file_name": "prompts.json"},
            "incident_pairs": {
                "file_name": "pairs.json",
                "ranking": True,
                "columns": {"prompt": "instruction", "chosen": "chosen", "rejected": "rejected"},
            },
            "incident_kto": {
                "file_name": "kto.json",
                "formatting": "sharegpt",
                "columns": {"messages": "conversations", "kto_tag": "kto_tag"},
            },
            "incident_images": {
                "file_name": "images.json",
                "formatting": "sharegpt",
                "columns": {"messages": "conversations", "images": "images"},
            },
        },
    )
    for name, recipe in recipes().items():
        write(
            configs / f"{name}.yaml",
            "# "
            + recipe["description"]
            + "\n"
            + yaml.safe_dump(recipe["config"], allow_unicode=True, sort_keys=False),
        )
    write_json(
        configs / "deepspeed_zero2.json",
        {
            "train_batch_size": "auto",
            "train_micro_batch_size_per_gpu": "auto",
            "gradient_accumulation_steps": "auto",
            "fp16": {"enabled": "auto"},
            "zero_optimization": {"stage": 2, "overlap_comm": True, "contiguous_gradients": True},
        },
    )
    print(f"학습 데이터와 {len(recipes())}개 설정 준비: {FACTORY}")


def validate() -> list[str]:
    info = read_json(FACTORY / "data" / "dataset_info.json")
    datasets = {}
    for name, meta in info.items():
        rows = read_json(FACTORY / "data" / meta["file_name"])
        if not rows:
            raise ValueError(f"빈 데이터셋: {name}")
        for row in rows:
            if meta.get("ranking") and (not row.get("chosen") or not row.get("rejected")):
                raise ValueError(f"선호 데이터에 chosen/rejected 누락: {name}")
            for key in meta.get("columns", {}).values():
                if key not in row:
                    raise ValueError(f"{name}: 데이터 열 누락 {key}")
            if "kto_tag" in row and not isinstance(row["kto_tag"], bool):
                raise ValueError("kto_tag는 bool이어야 합니다.")
            for picture in row.get("images", []):
                if not (FACTORY / "data" / picture).is_file():
                    raise ValueError(f"이미지 누락: {picture}")
            if "images" in row:
                count = sum(m["value"].count("<image>") for m in row["conversations"])
                if count != len(row["images"]):
                    raise ValueError("<image> 토큰 수와 이미지 수가 다릅니다.")
        datasets[name] = rows
    train_questions = {r["instruction"] for r in datasets["incident_train"]}
    if train_questions & {r["instruction"] for r in datasets["incident_eval"]}:
        raise ValueError("학습과 검증 질문이 중복됩니다.")
    checked = []
    for name, recipe in recipes().items():
        config = yaml.safe_load((FACTORY / "configs" / f"{name}.yaml").read_text(encoding="utf-8"))
        for key in ("dataset", "eval_dataset"):
            for ds in str(config.get(key, "")).split(","):
                if ds and ds not in info:
                    raise ValueError(f"{name}: 등록되지 않은 데이터셋 {ds}")
        if recipe["command"] == "train":
            stage = config["stage"]
            if stage not in {"pt", "sft", "rm", "ppo", "dpo", "kto"}:
                raise ValueError(f"{name}: 잘못된 stage")
            if stage in {"dpo", "rm"} and not info[config["dataset"]].get("ranking"):
                raise ValueError(f"{name}: preference dataset이 필요합니다.")
            if stage == "ppo" and not config.get("reward_model"):
                raise ValueError("PPO reward_model 누락")
            if config.get("use_cpu") and (config.get("fp16") or config.get("bf16")):
                raise ValueError("CPU 예제에서는 혼합 정밀도를 끄세요.")
            if config.get("do_predict") and not config.get("predict_with_generate"):
                raise ValueError("predict_with_generate가 필요합니다.")
            if config.get("quantization_bit") and config.get("finetuning_type") != "lora":
                raise ValueError("이 실습의 양자화 학습은 LoRA용입니다.")
        if recipe["command"] == "export" and config.get("quantization_bit"):
            raise ValueError("LoRA 병합 시 quantization_bit을 제거하세요.")
        checked.append(name)
    print(f"데이터셋 {len(info)}개 / 설정 {len(checked)}개 정적 검증 통과 (실제 모델 학습 아님)")
    return checked


def run_recipe(name: str, execute=False):
    if name == "webui":
        command = ["llamafactory-cli", "webui"]
        recipe = {"requires": []}
        config = {}
    else:
        available = recipes()
        if name not in available:
            raise ValueError(f"알 수 없는 recipe: {name}; factory list로 확인하세요.")
        recipe = available[name]
        path = FACTORY / "configs" / f"{name}.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        command = ["llamafactory-cli", recipe["command"], str(path.relative_to(ROOT))]
    # Follow edited YAML paths, so the CPU recipe can also feed chat/export/evaluation.
    dependencies = []
    for key, marker in (
        ("adapter_name_or_path", "adapter_config.json"),
        ("reward_model", "adapter_config.json"),
        ("resume_from_checkpoint", "trainer_state.json"),
    ):
        if config.get(key):
            dependencies.append(str(Path(config[key]) / marker))
    if name == "api_vllm":
        dependencies.append(str(Path(config["model_name_or_path"]) / "config.json"))
    print("실행 위치:", ROOT)
    print("명령:", " ".join(command))
    if dependencies:
        print("선행 결과:", ", ".join(dependencies))
    if not execute:
        print("미리보기입니다. 실제 실행: 같은 명령에 --execute 추가")
        return command
    if not shutil.which("llamafactory-cli"):
        raise ValueError("factory/README.md에 따라 별도 환경에 LLaMA-Factory를 설치하세요.")
    for dependency in dependencies:
        if not (ROOT / dependency).exists():
            raise ValueError(f"선행 실습 결과가 없습니다: {dependency}")
    for field in ("output_dir", "export_dir"):
        destination = ROOT / config[field] if config.get(field) else None
        if destination and destination.exists() and any(destination.iterdir()):
            if not config.get("resume_from_checkpoint"):
                raise ValueError(
                    f"기존 결과 보호: {destination}. YAML에 새 출력 경로를 지정하세요."
                )
    env = os.environ.copy()
    if name in {"sft_ddp", "sft_deepspeed"}:
        env["FORCE_TORCHRUN"] = "1"
        env.setdefault("NPROC_PER_NODE", "2")
    env.setdefault("API_PORT", "8000")
    env.setdefault("API_HOST", "127.0.0.1")
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    return command


def dispatch(args):
    if args.step == "prepare":
        prepare(args.force)
    elif args.step == "validate":
        validate()
    elif args.step == "list":
        for name, recipe in recipes().items():
            print(f"{name:20s} {recipe['description']}")
        print(f"{'webui':20s} LLaMA Board 웹 UI")
    else:
        run_recipe(args.recipe, args.execute)
