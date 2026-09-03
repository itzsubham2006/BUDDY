"""
Build script: packages Jarvis into a standalone Windows executable using
PyInstaller.

Run on Windows (PyInstaller builds must run on the target OS):

    python scripts/build.py

Output lands in `dist/Jarvis/Jarvis.exe`. This is deliberately a thin
wrapper around PyInstaller rather than a hand-rolled packager, since
PyInstaller already solves dependency bundling correctly.

NOTE: This is scaffolding for Phase 10 (packaging). Before running it for
a real release, add an application icon at `assets/icon.ico` and review
the `--add-data` list below for anything new the app has started reading
from disk at runtime.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if platform.system() != "Windows":
        print(
            "This build script produces a Windows executable and must be run "
            "on Windows. Aborting on this platform."
        )
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Run: pip install pyinstaller")
        return 1

    entry_point = PROJECT_ROOT / "app" / "main.py"
    icon_path = PROJECT_ROOT / "assets" / "icon.ico"

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "Jarvis",
        "--noconsole",
        "--onedir",
        "--add-data",
        f"{PROJECT_ROOT / 'config' / 'config.example.yaml'};config",
        str(entry_point),
    ]
    if icon_path.exists():
        args.extend(["--icon", str(icon_path)])

    print("Running:", " ".join(args))
    result = subprocess.run(args, cwd=str(PROJECT_ROOT))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
