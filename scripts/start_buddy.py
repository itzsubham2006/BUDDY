"""
Starts Buddy in the background as a detached Windows process.
You can close VS Code, your terminal, and all windows — Buddy will stay running.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Use buddenv python
venv_python = PROJECT_ROOT / "buddenv" / "Scripts" / "python.exe"
if venv_python.exists():
    python_exe = venv_python
else:
    python_exe = Path(sys.executable)

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


def main() -> int:
    cmd = [str(python_exe), "-u", "-m", "app.main", "--voice"]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["FOR_DISABLE_CONSOLE_CTRL_HANDLER"] = "1"
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    # Launch detached process with independent system handles
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )

    # Save PID so stop_buddy.py can terminate it cleanly
    pid_file = PROJECT_ROOT / "data" / "buddy.pid"
    pid_file.write_text(str(proc.pid), encoding="utf-8")

    print(f"[OK] Buddy started in background (PID: {proc.pid})!")
    print("     You can now close VS Code, IDE, and all windows.")
    print("     Say 'Hi Buddy' anytime to give commands!")
    print("\nTo stop Buddy later, run:")
    print("     python scripts/stop_buddy.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
