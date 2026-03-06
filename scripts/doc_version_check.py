#!/usr/bin/env python3
"""Verify required docs include doc_version metadata."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCS = [
    "README.md",
    "CONTRIBUTING.md",
    "docs/runbook.md",
    "docs/indexer-operations.md",
    "docs/release-checklist.md",
    "docs/reports/2026-03-05-btwin-openclaw-qa.md",
    "docs/plans/2026-03-05-runtime-modes-and-core-ports.md",
    "docs/glossary.md",
]

DOC_VERSION_RE = re.compile(r"^doc_version\s*:\s*([0-9]+)\s*$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that managed docs include a numeric doc_version field."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional file paths to check. If omitted, checks the default managed docs.",
    )
    return parser.parse_args()


def validate(paths: list[Path]) -> tuple[int, list[str]]:
    errors: list[str] = []
    for path in paths:
        if not path.exists():
            errors.append(f"[missing] {path}")
            continue

        text = path.read_text(encoding="utf-8")
        match = DOC_VERSION_RE.search(text)
        if not match:
            errors.append(f"[no-doc_version] {path}")
            continue

        version = int(match.group(1))
        if version < 1:
            errors.append(f"[invalid-doc_version] {path} (found: {version})")

    return len(errors), errors


def main() -> int:
    args = parse_args()
    rel_paths = args.paths if args.paths else DEFAULT_DOCS
    paths = [(ROOT / p).resolve() for p in rel_paths]

    count, errors = validate(paths)
    if count:
        print("doc_version check FAILED")
        for err in errors:
            print(f" - {err}")
        return 1

    print(f"doc_version check OK ({len(paths)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
