#!/usr/bin/env python3
"""Build a standalone single-file executable for exiur."""

import os
import subprocess
import sys
import platform
from pathlib import Path

ROOT = Path(__file__).parent
SPEC = ROOT / "exiur.spec"
DIST = ROOT / "dist"


def main() -> None:
    if not SPEC.exists():
        print(f"Error: {SPEC} not found", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC)]

    print(f"Building exiur for {platform.system()} {platform.machine()}...")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("Build failed.", file=sys.stderr)
        sys.exit(1)

    name = "exiur.exe" if platform.system() == "Windows" else "exiur"
    out = DIST / name
    if out.exists():
        size_mb = out.stat().st_size / (1024 * 1024)
        print(f"\nBuild complete: {out} ({size_mb:.1f} MB)")
    else:
        print(f"\nBuild complete, but expected output not found at {out}")


if __name__ == "__main__":
    main()
