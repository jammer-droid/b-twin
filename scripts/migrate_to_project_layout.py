#!/usr/bin/env python3
"""Migrate existing B-TWIN entries to project-partitioned layout.

Moves entries from flat layout:
    entries/{date}/slug.md
    entries/convo/{date}/slug.md
    entries/collab/{date}/slug.md

To project-partitioned layout:
    entries/_global/{date}/slug.md
    entries/_global/convo/{date}/slug.md
    entries/_global/collab/{date}/slug.md
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FRAMEWORK_DIRS = {"convo", "collab", "global"}


def _add_project_to_frontmatter(file_path: Path) -> bool:
    """Add project: _global to frontmatter if not already present.

    Returns True if file was modified.
    """
    text = file_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return False

    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        return False

    frontmatter = text[4:end_idx]
    if "project:" in frontmatter:
        return False  # Already has project field

    # Add project field after existing frontmatter fields
    new_frontmatter = frontmatter + "\nproject: _global"
    new_text = f"---\n{new_frontmatter}\n---\n{text[end_idx + 5:]}"
    file_path.write_text(new_text, encoding="utf-8")
    return True


def migrate(data_dir: Path, *, dry_run: bool = False) -> dict:
    """Run the migration.

    Returns dict with:
        - moved: number of directories/files moved
        - updated: number of files with frontmatter updated
        - skipped: bool, True if already migrated
        - errors: list of error messages
    """
    entries_dir = data_dir / "entries"
    global_dir = entries_dir / "_global"

    result: dict = {"moved": 0, "updated": 0, "skipped": False, "errors": []}

    if not entries_dir.exists():
        result["errors"].append(f"entries directory not found: {entries_dir}")
        return result

    if global_dir.exists():
        result["skipped"] = True
        return result

    # Collect items to move
    items_to_move: list[tuple[Path, Path]] = []

    for item in sorted(entries_dir.iterdir()):
        if item.name.startswith("_"):
            continue  # Skip _global itself or other _ prefixed
        if item.name.startswith("."):
            continue

        if DATE_PATTERN.match(item.name) and item.is_dir():
            # Date directory: entries/2026-03-06/ -> entries/_global/2026-03-06/
            items_to_move.append((item, global_dir / item.name))
        elif item.name in FRAMEWORK_DIRS and item.is_dir():
            # Framework directory: entries/convo/ -> entries/_global/convo/
            items_to_move.append((item, global_dir / item.name))

    if not items_to_move:
        return result

    if dry_run:
        for src, dst in items_to_move:
            print(f"[DRY-RUN] Would move: {src} -> {dst}")
        result["moved"] = len(items_to_move)
        return result

    # Create _global directory
    global_dir.mkdir(parents=True, exist_ok=True)

    # Move items
    for src, dst in items_to_move:
        try:
            shutil.move(str(src), str(dst))
            result["moved"] += 1
        except Exception as e:
            result["errors"].append(f"Failed to move {src}: {e}")

    # Update frontmatter in all .md files under _global
    for md_file in global_dir.rglob("*.md"):
        try:
            if _add_project_to_frontmatter(md_file):
                result["updated"] += 1
        except Exception as e:
            result["errors"].append(f"Failed to update frontmatter {md_file}: {e}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate B-TWIN entries to project layout",
    )
    parser.add_argument(
        "--data-dir",
        default=str(Path.home() / ".btwin"),
        help="B-TWIN data directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without executing",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print(f"Migrating entries in {data_dir}/entries/ to _global/ layout...")

    result = migrate(data_dir, dry_run=args.dry_run)

    if result["skipped"]:
        print("Migration skipped: _global/ already exists (already migrated)")
        sys.exit(0)

    if result["errors"]:
        for err in result["errors"]:
            print(f"ERROR: {err}", file=sys.stderr)

    print(f"Moved: {result['moved']} directories")
    print(f"Updated frontmatter: {result['updated']} files")

    if not args.dry_run and result["moved"] > 0:
        print("\nNext steps:")
        print("  btwin indexer reconcile  -- Re-scan and index migrated documents")
        print("  btwin indexer refresh    -- Process any pending documents")


if __name__ == "__main__":
    main()
