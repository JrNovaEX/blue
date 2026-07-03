#!/usr/bin/env python3
"""Build a cross-platform standalone .pyz file for exiur."""

import compileall
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
SRC = ROOT / "exiur"

DEPS = [
    "click", "rich", "requests",
    "certifi", "charset_normalizer", "idna", "urllib3",
    "pygments", "markdown_it", "mdurl",
]


def find_site_packages() -> Path:
    for p in ROOT.glob(".venv/lib/python*/site-packages"):
        if p.is_dir():
            return p
    for p in ROOT.glob("venv/lib/python*/site-packages"):
        if p.is_dir():
            return p
    raise RuntimeError("No site-packages found in .venv or venv")


def main() -> None:
    DIST.mkdir(exist_ok=True)
    out = DIST / "exiur.pyz"
    site = find_site_packages()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pkg = tmp / "exiur"

        shutil.copytree(SRC, pkg)
        compileall.compile_dir(str(pkg), optimize=2, quiet=1)

        (tmp / "__main__.py").write_text("from exiur.cli import main\nmain()\n")

        deps_dir = tmp / "_deps"
        deps_dir.mkdir()

        for dep in DEPS:
            src = site / dep
            if src.is_dir():
                shutil.copytree(src, deps_dir / dep)
            else:
                print(f"Warning: {dep} not found in site-packages")

        import zipfile
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(deps_dir.rglob("*")):
                if f.is_file():
                    zf.write(f, f.relative_to(deps_dir))

            for f in sorted(tmp.rglob("*")):
                if f.is_file() and "_deps" not in f.parts:
                    zf.write(f, f.relative_to(tmp))

        size_kb = out.stat().st_size / 1024
        print(f"Build complete: {out} ({size_kb:.0f} KB)")
        print(f"Run with: python {out.name}")


if __name__ == "__main__":
    main()
