#!/usr/bin/env python3
"""Build a cross-platform standalone .pyz file for exiur."""

import compileall
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
SRC = ROOT / "exiur"


def main() -> None:
    DIST.mkdir(exist_ok=True)
    out = DIST / "exiur.pyz"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pkg = tmp / "exiur"

        # Copy source
        shutil.copytree(SRC, pkg)

        # Compile to .pyc
        compileall.compile_dir(str(pkg), optimize=2, quiet=1)

        # Copy entry point
        (tmp / "__main__.py").write_text("from exiur.cli import main\nmain()\n")

        # Bundle dependencies into the zip
        import subprocess
        deps_dir = tmp / "_deps"
        deps_dir.mkdir()
        subprocess.check_call([
            "uv", "pip", "install",
            "--python", ".venv/bin/python",
            "--target", str(deps_dir),
            "click>=8.1", "rich>=13.0", "requests>=2.31",
            "--quiet"
        ], cwd=str(ROOT))

        # Create .pyz zip
        import zipfile
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add deps first (lower priority in zip)
            for f in sorted(deps_dir.rglob("*")):
                if f.is_file():
                    arcname = f.relative_to(deps_dir)
                    zf.write(f, arcname)

            # Add app code (higher priority)
            for f in sorted(tmp.rglob("*")):
                if f.is_file() and "_deps" not in f.parts:
                    arcname = f.relative_to(tmp)
                    zf.write(f, arcname)

        size_kb = out.stat().st_size / 1024
        print(f"Build complete: {out} ({size_kb:.0f} KB)")
        print(f"Run with: python {out.name}")


if __name__ == "__main__":
    main()
