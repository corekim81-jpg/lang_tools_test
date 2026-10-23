#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
command -v uv >/dev/null || { echo 'Install uv first: python3 -m pip install uv'; exit 1; }
uv sync --frozen --cache-dir .cache/uv
if [ ! -f .env ]; then cp .env.example .env; fi
.venv/bin/python -m lab factory prepare
.venv/bin/python -m lab doctor
