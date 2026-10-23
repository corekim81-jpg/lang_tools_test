$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv가 필요합니다. python -m pip install uv 실행 후 다시 시작하세요.'
}
uv sync --frozen --cache-dir .cache/uv
if ($LASTEXITCODE -ne 0) { throw '패키지 설치 실패' }
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
& .venv/Scripts/python.exe -m lab factory prepare
if ($LASTEXITCODE -ne 0) { throw '실습 데이터 준비 실패' }
& .venv/Scripts/python.exe -m lab doctor
