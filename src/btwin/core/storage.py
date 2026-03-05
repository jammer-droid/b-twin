"""Markdown file storage for B-TWIN entries."""

from pathlib import Path

import yaml

from btwin.core.collab_models import CollabRecord
from btwin.core.models import Entry


class Storage:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.entries_dir = data_dir / "entries"
        self.collab_entries_dir = self.entries_dir / "collab"

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

    def save_collab_record(self, record: CollabRecord) -> Path:
        """Save a collab record under entries/collab/YYYY-MM-DD/."""
        day = record.created_at.date().isoformat()
        date_dir = self.collab_entries_dir / day
        date_dir.mkdir(parents=True, exist_ok=True)

        safe_task = record.task_id.replace("/", "-")
        file_path = date_dir / f"{safe_task}-{record.status}-{record.record_id}.md"

        frontmatter = yaml.dump(
            record.model_dump(by_alias=True, mode="json"),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).strip()

        body_lines = [record.summary, "", "## Evidence"]
        body_lines.extend([f"- {item}" for item in record.evidence])
        body_lines.append("")
        body_lines.append("## Next Action")
        body_lines.extend([f"- {item}" for item in record.next_action])
        body = "\n".join(body_lines)

        file_path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n")
        return file_path

    def read_collab_record(self, record_id: str) -> CollabRecord | None:
        """Read a collab record by record id."""
        if not self.collab_entries_dir.exists():
            return None

        for file_path in sorted(self.collab_entries_dir.glob("*/*.md")):
            raw = file_path.read_text()
            parsed = self._parse_collab_frontmatter(raw)
            if parsed and parsed.record_id == record_id:
                return parsed
        return None

    def list_collab_records(self) -> list[CollabRecord]:
        """List all collab records."""
        records: list[CollabRecord] = []
        if not self.collab_entries_dir.exists():
            return records

        for file_path in sorted(self.collab_entries_dir.glob("*/*.md")):
            parsed = self._parse_collab_frontmatter(file_path.read_text())
            if parsed:
                records.append(parsed)
        return records

    @staticmethod
    def _parse_collab_frontmatter(raw: str) -> CollabRecord | None:
        if not raw.startswith("---\n"):
            return None
        parts = raw.split("---\n", 2)
        if len(parts) < 3:
            return None

        metadata = yaml.safe_load(parts[1]) or {}
        try:
            return CollabRecord.model_validate(metadata)
        except Exception:
            return None
