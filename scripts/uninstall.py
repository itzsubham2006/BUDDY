"""
Uninstall helper: disables Windows autostart (if enabled) and optionally
removes local data (logs, memory, config, .env).

Run:
    python scripts/uninstall.py
"""

from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if platform.system() == "Windows":
        try:
            from app.desktop.startup import disable_startup, is_startup_enabled

            if is_startup_enabled():
                disable_startup()
                print("Removed Jarvis from Windows startup.")
            else:
                print("Jarvis was not registered for startup.")
        except Exception as exc:  # noqa: BLE001
            print(f"Could not update startup registration: {exc}")
    else:
        print("Not running on Windows; skipping startup deregistration.")

    answer = input(
        "Delete local data (logs, memory, config, .env)? [y/N]: "
    ).strip().lower()
    if answer == "y":
        for path in [
            PROJECT_ROOT / "data" / "logs",
            PROJECT_ROOT / "data" / "memory",
            PROJECT_ROOT / "config" / "config.yaml",
            PROJECT_ROOT / ".env",
        ]:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        print("Local data removed.")
    else:
        print("Local data kept.")

    print("Uninstall steps complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
