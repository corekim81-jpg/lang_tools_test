"""One entry point for all labs; every network write requires an explicit live command."""

import argparse
import importlib.metadata
import json
import os
import shutil
import sys

from lab.common import ROOT, load_env


def doctor() -> None:
    versions = {}
    for package in ("langsmith", "langfuse", "langchain-core", "openai", "llamafactory"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed in this environment"
    print(
        json.dumps(
            {
                "root": str(ROOT),
                "python": sys.version.split()[0],
                "packages": versions,
                "commands": {
                    key: bool(shutil.which(key))
                    for key in ("docker", "nvidia-smi", "llamafactory-cli")
                },
                "credentials_present": {
                    key: bool(os.getenv(key))
                    for key in (
                        "LANGSMITH_API_KEY",
                        "LANGFUSE_PUBLIC_KEY",
                        "LANGFUSE_SECRET_KEY",
                    )
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main(argv=None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description="세 도구의 기능별 실습 — README.md 참고")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="버전, 실행 도구, 키 설정 여부만 확인")
    commands.add_parser("offline", help="외부 연결 없는 공통 파이프라인·평가 실습")
    model = commands.add_parser("model", help="관찰 서비스 없이 실제 모델 서버 연결 확인")
    model.add_argument("step", choices=["models", "chat"])
    model.add_argument("--live", action="store_true", help="설정된 모델 서버 호출")
    model.add_argument("--save-model", action="store_true", help="단일 모델 ID를 .env에 저장")
    model.add_argument("--stream", action="store_true", help="대화 응답 스트리밍")
    model.add_argument("--question", default="CPU가 95%까지 올라갔어요. 무엇을 확인하나요?")
    for tool, steps in {
        "langsmith": [
            "trace",
            "async",
            "prompts",
            "dataset",
            "evaluate",
            "compare",
            "feedback",
            "query",
            "integrations",
            "judge",
            "all",
        ],
        "langfuse": [
            "trace",
            "async",
            "prompts",
            "dataset",
            "evaluate",
            "scores",
            "query",
            "integrations",
            "media",
            "judge",
            "all",
        ],
    }.items():
        sub = commands.add_parser(tool)
        sub.add_argument("step", choices=steps)
        sub.add_argument("--live", action="store_true", help="설정된 서비스에 실습 데이터를 기록")
        sub.add_argument(
            "--model", choices=["mock", "api"], default=os.getenv("LAB_MODEL_MODE", "mock")
        )
    factory = commands.add_parser("factory", help="LLaMA-Factory 설정 생성·검증·실행")
    factory.add_argument("step", choices=["list", "prepare", "validate", "run"])
    factory.add_argument("--recipe", default="sft_lora")
    factory.add_argument("--execute", action="store_true", help="실제 학습/추론 프로세스 시작")
    factory.add_argument("--force", action="store_true", help="prepare 시 기존 생성 파일 덮어쓰기")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            doctor()
        elif args.command == "offline":
            from lab.offline import run

            run()
        elif args.command == "model":
            if not args.live:
                parser.error("모델 서버 호출에는 --live를 붙이세요.")
            if args.save_model and args.step != "models":
                parser.error("--save-model은 models 명령에서만 사용합니다.")
            if args.stream and args.step != "chat":
                parser.error("--stream은 chat 명령에서만 사용합니다.")
            from lab.model_demo import run

            run(args)
        elif args.command == "factory":
            from lab.factory import dispatch

            dispatch(args)
        else:
            if not args.live:
                parser.error(
                    "실제 서비스 실습에는 --live를 붙이세요. 키 없는 실습: python -m lab offline"
                )
            if args.step in {"integrations", "judge"} and args.model != "api":
                parser.error("이 실습은 --model api와 LLM_* 설정이 필요합니다.")
            if args.command == "langsmith":
                from lab.langsmith_demo import run
            else:
                from lab.langfuse_demo import run
            run(args.step, args.model)
    except (ValueError, FileNotFoundError, ImportError) as exc:
        print(f"실행 조건 확인: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
