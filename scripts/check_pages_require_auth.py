#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    pages_dir = root / "pages"
    page_files = sorted(pages_dir.glob("*.py"))

    missing: list[str] = []
    for page in page_files:
        content = page.read_text(encoding="utf-8", errors="ignore")
        if "require_auth(" not in content:
            missing.append(str(page.relative_to(root)))

    if missing:
        print("ERROR: missing require_auth(...) in:")
        for path in missing:
            print(f"- {path}")
        return 1

    print(f"OK: require_auth(...) found in all {len(page_files)} page files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
