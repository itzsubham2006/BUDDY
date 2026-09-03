"""
Interactive first-run setup: creates `.env` and `config/config.yaml` from
the example files if they don't already exist, and prompts for the
minimum values needed to start Jarvis (LLM provider + API key).

Run:
    python scripts/install.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _copy_if_missing(example: Path, target: Path) -> bool:
    if target.exists():
        return False
    shutil.copyfile(example, target)
    return True


def main() -> int:
    env_example = PROJECT_ROOT / ".env.example"
    env_target = PROJECT_ROOT / ".env"
    config_example = PROJECT_ROOT / "config" / "config.example.yaml"
    config_target = PROJECT_ROOT / "config" / "config.yaml"

    created_env = _copy_if_missing(env_example, env_target)
    created_config = _copy_if_missing(config_example, config_target)

    (PROJECT_ROOT / "data" / "logs").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data" / "memory").mkdir(parents=True, exist_ok=True)

    print("Jarvis setup")
    print("============")
    print(f"[{'created' if created_env else 'exists '}] {env_target}")
    print(f"[{'created' if created_config else 'exists '}] {config_target}")

    if created_env:
        api_key = input(
            "\nEnter your LLM API key (e.g. Anthropic API key), or leave blank to "
            "set it later in .env: "
        ).strip()
        if api_key:
            content = env_target.read_text(encoding="utf-8")
            content = content.replace("LLM_API_KEY=\n", f"LLM_API_KEY={api_key}\n")
            env_target.write_text(content, encoding="utf-8")
            print("API key saved to .env (this file is git-ignored).")

    print(
        "\nSetup complete. Review config/config.yaml for application paths, "
        "then run: python -m app.main"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
