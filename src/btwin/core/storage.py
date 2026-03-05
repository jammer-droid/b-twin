"""Markdown file storage for B-TWIN entries."""

from pathlib import Path

import yaml

from btwin.core.models import Entry


class Storage:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.entries_dir = data_dir / "entries"

    def save_entry(self, entry: Entry) -> Path:
        """Save an entry. If same date/slug exists, merge content and tags."""
        date_dir = self.entries_dir / entry.date
        date_dir.mkdir(parents=True, exist_ok=True)
        file_path = date_dir / f"{entry.slug}.md"

        merged_metadata = dict(entry.metadata)
        merged_content = entry.content

        if file_path.exists():
            existing = self._parse_file(file_path.read_text(), entry.date, entry.slug)
            merged_content = existing.content.rstrip() + "\n\n---\n\n" + entry.content
            merged_metadata = dict(existing.metadata)
            merged_metadata.update(entry.metadata)
            existing_tags = existing.metadata.get("tags", [])
            new_tags = entry.metadata.get("tags", [])
            if existing_tags or new_tags:
                merged_metadata["tags"] = list(dict.fromkeys(
                    list(existing_tags) + list(new_tags)
                ))

        fm = dict(merged_metadata)
        fm["date"] = entry.date
        fm["slug"] = entry.slug
        frontmatter = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()

        file_path.write_text(f"---\n{frontmatter}\n---\n\n{merged_content}")
        return file_path

    def _parse_file(self, raw: str, date: str, slug: str) -> Entry:
        """Parse a markdown file, extracting frontmatter if present."""
        if raw.startswith("---\n"):
            parts = raw.split("---\n", 2)
            if len(parts) >= 3:
                fm_text = parts[1]
                content = parts[2].lstrip("\n")
                metadata = yaml.safe_load(fm_text) or {}
                # Keep structured metadata types (lists/labels/links),
                # but normalize canonical scalar fields to strings.
                if "date" in metadata:
                    metadata["date"] = str(metadata["date"])
                if "slug" in metadata:
                    metadata["slug"] = str(metadata["slug"])
                return Entry(date=date, slug=slug, content=content, metadata=metadata)
        # No frontmatter (backwards compatible)
        return Entry(date=date, slug=slug, content=raw)

    def list_entries(self) -> list[Entry]:
        """List all saved entries."""
        entries = []
        if not self.entries_dir.exists():
            return entries
        for date_dir in sorted(self.entries_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            for md_file in sorted(date_dir.glob("*.md")):
                raw = md_file.read_text()
                entries.append(self._parse_file(raw, date_dir.name, md_file.stem))
        return entries

    def read_entry(self, date: str, slug: str) -> Entry | None:
        """Read a specific entry by date and slug."""
        file_path = self.entries_dir / date / f"{slug}.md"
        if not file_path.exists():
            return None
        raw = file_path.read_text()
        return self._parse_file(raw, date, slug)
