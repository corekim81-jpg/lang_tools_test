"""Create credentials for the local-only Compose lab; never overwrite an existing .env."""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    target = ROOT / "infra" / ".env"
    if target.exists():
        print("infra/.env already exists; keeping its credentials and existing volumes.")
        return
    public = "pk-lf-" + secrets.token_hex(16)
    secret = "sk-lf-" + secrets.token_hex(24)
    values = {
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "CLICKHOUSE_PASSWORD": secrets.token_hex(24),
        "REDIS_AUTH": secrets.token_hex(24),
        "MINIO_ROOT_PASSWORD": secrets.token_hex(24),
        "SALT": secrets.token_hex(24),
        "ENCRYPTION_KEY": secrets.token_hex(32),
        "NEXTAUTH_SECRET": secrets.token_hex(32),
        "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": public,
        "LANGFUSE_INIT_PROJECT_SECRET_KEY": secret,
        "LANGFUSE_INIT_USER_EMAIL": "demo@localhost.test",
        "LANGFUSE_INIT_USER_PASSWORD": secrets.token_urlsafe(24),
    }
    target.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8")
    from dotenv import dotenv_values

    app_env = ROOT / ".env"
    existing = dotenv_values(app_env) if app_env.exists() else {}
    if not existing.get("LANGFUSE_PUBLIC_KEY") and not existing.get("LANGFUSE_SECRET_KEY"):
        text = (
            app_env.read_text(encoding="utf-8")
            if app_env.exists()
            else (ROOT / ".env.example").read_text(encoding="utf-8")
        )
        # Preserve all unrelated settings, including an existing LangSmith key.
        replacements = {
            "LANGFUSE_PUBLIC_KEY": public,
            "LANGFUSE_SECRET_KEY": secret,
            "LANGFUSE_BASE_URL": "http://localhost:3000",
        }
        lines = [
            line for line in text.splitlines() if line.split("=", 1)[0].strip() not in replacements
        ]
        lines += [f"{k}={v}" for k, v in replacements.items()]
        app_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("Local SDK keys configured in .env")
    else:
        print("Existing .env Langfuse credentials preserved. Local keys are in infra/.env.")
    print("Login email: demo@localhost.test; password: LANGFUSE_INIT_USER_PASSWORD in infra/.env")
    print("Start: docker compose --env-file infra/.env -f infra/compose.yaml up -d")


if __name__ == "__main__":
    main()
