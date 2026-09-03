"""
Stops the background Buddy assistant process.
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_ROOT / "data" / "buddy.pid"


def main() -> int:
    if not PID_FILE.exists():
        print("No running Buddy background PID file found.")
        os.system('taskkill /F /FI "IMAGENAME eq pythonw.exe" 2>nul')
        print("[OK] Ensured any background pythonw Buddy instances are stopped.")
        return 0

    try:
        pid_str = PID_FILE.read_text(encoding="utf-8").strip()
        pid = int(pid_str)
        os.system(f"taskkill /PID {pid} /F 2>nul")
        PID_FILE.unlink(missing_ok=True)
        print(f"[OK] Stopped Buddy background process (PID: {pid}).")
    except Exception as exc:
        print(f"Error stopping process: {exc}")
        os.system('taskkill /F /FI "IMAGENAME eq pythonw.exe" 2>nul')
        PID_FILE.unlink(missing_ok=True)
        print("[OK] Stopped Buddy instances.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
