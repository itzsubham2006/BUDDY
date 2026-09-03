"""
Helper script to enable or disable Buddy starting automatically when your PC turns on.

Usage:
    python scripts/setup_startup.py --enable
    python scripts/setup_startup.py --disable
    python scripts/setup_startup.py --status
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.desktop.startup import disable_startup, enable_startup, is_startup_enabled


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Buddy Windows Startup")
    parser.add_argument("--enable", action="store_true", help="Enable Buddy to start when Windows boots")
    parser.add_argument("--disable", action="store_true", help="Disable Buddy from starting with Windows")
    parser.add_argument("--status", action="store_true", help="Check if startup is currently enabled")

    args = parser.parse_args()

    if args.enable:
        cmd = enable_startup()
        print("[OK] Buddy Windows Auto-Start ENABLED!")
        print(f"     Command: {cmd}")
        print("     Buddy will now start in the background listening for 'Hi Buddy' whenever you turn on your PC.")
        return 0

    if args.disable:
        disable_startup()
        print("[OK] Buddy Windows Auto-Start DISABLED.")
        return 0

    # Default or status check
    enabled = is_startup_enabled()
    print(f"Buddy Windows Auto-Start Status: {'ENABLED' if enabled else 'DISABLED'}")
    if not enabled:
        print("\nTo enable auto-start on PC boot, run:")
        print("    python scripts/setup_startup.py --enable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
