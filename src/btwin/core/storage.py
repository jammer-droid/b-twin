"""Markdown file storage for B-TWIN entries."""

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import yaml

from btwin.core.collab_models import CollabRecord
from btwin.core.document_contracts import validate_document_contract
from btwin.core.models import Entry

_FRAMEWORK_DIRS = {"convo", "collab", "global"}


class Storage:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.entries_dir = data_dir / "entries"
        self.convo_entries_dir = self.entries_dir / "convo"
        self.collab_entries_dir = self.entries_dir / "collab"
        self.promoted_entries_dir = self.entries_dir / "global"

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
        self._ensure_contract("entry", fm)
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
            if date_dir.name in _FRAMEWORK_DIRS:
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

    def save_convo_record(
        self,
        *,
        content: str,
        requested_by_user: bool = False,
        topic: str | None = None,
        created_at: datetime | None = None,
    ) -> Entry:
        """Save explicit conversation memory under entries/convo/YYYY-MM-DD/."""
        now = created_at or datetime.now(timezone.utc)
        date = now.strftime("%Y-%m-%d")
        slug = f"convo-{now.strftime('%H%M%S%f')}"

        date_dir = self.convo_entries_dir / date
        date_dir.mkdir(parents=True, exist_ok=True)
        file_path = date_dir / f"{slug}.md"

        metadata: dict[str, object] = {
            "date": date,
            "slug": slug,
            "recordType": "convo",
            "requestedByUser": requested_by_user,
            "created_at": now.isoformat(),
        }
        if topic:
            metadata["topic"] = topic

        self._ensure_contract("convo", metadata)
        frontmatter = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()
        file_path.write_text(f"---\n{frontmatter}\n---\n\n{content}\n")
        return Entry(date=date, slug=slug, content=content, metadata=metadata)

    def list_convo_entries(self) -> list[Entry]:
        """List explicit convo records."""
        entries: list[Entry] = []
        if not self.convo_entries_dir.exists():
            return entries

        for date_dir in sorted(self.convo_entries_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            for md_file in sorted(date_dir.glob("*.md")):
                raw = md_file.read_text()
                entries.append(self._parse_file(raw, date_dir.name, md_file.stem))
        return entries

    def save_collab_record(self, record: CollabRecord) -> Path:
        """Save a collab record under entries/collab/YYYY-MM-DD/."""
        file_path = self._collab_path(record)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        metadata = record.model_dump(by_alias=True, mode="json")
        self._ensure_contract("collab", metadata)
        frontmatter = yaml.dump(
            metadata,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        body = self._render_collab_body(record)

        file_path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n")
        return file_path

    def read_collab_record(self, record_id: str) -> CollabRecord | None:
        """Read a collab record by record id."""
        loaded = self._find_collab_file(record_id)
        if loaded is None:
            return None
        return loaded[0]

    def read_collab_record_document(self, record_id: str) -> dict[str, str | dict[str, object]] | None:
        """Read collab record with frontmatter and markdown body."""
        loaded = self._find_collab_file(record_id)
        if loaded is None:
            return None

        record, file_path, body = loaded
        return {
            "recordId": record.record_id,
            "path": str(file_path),
            "frontmatter": record.model_dump(by_alias=True, mode="json"),
            "content": body,
        }

    def update_collab_record(
        self,
        record_id: str,
        *,
        status: str,
        version: int,
        author_agent: str | None = None,
    ) -> CollabRecord | None:
        """Update status/version for an existing collab record."""
        loaded = self._find_collab_file(record_id)
        if loaded is None:
            return None

        existing, old_path, _body = loaded
        payload = existing.model_dump(by_alias=True, mode="json")
        payload["status"] = status
        payload["version"] = version
        if author_agent is not None:
            payload["authorAgent"] = author_agent

        updated = CollabRecord.model_validate(payload)
        new_path = self._collab_path(updated)
        self.save_collab_record(updated)
        if old_path != new_path and old_path.exists():
            old_path.unlink()
        return updated

    def list_collab_records(self) -> list[CollabRecord]:
        """List all collab records."""
        records: list[CollabRecord] = []
        for file_path in self._iter_collab_files():
            loaded = self._load_collab_file(file_path)
            if loaded is None:
                continue
            records.append(loaded[0])
        return records

    def save_promoted_entry(self, *, item_id: str, source_record_id: str, content: str) -> Path:
        """Save promoted global entry for a promotion item."""
        date_dir = self.promoted_entries_dir / "promoted"
        date_dir.mkdir(parents=True, exist_ok=True)

        file_path = date_dir / f"{item_id}.md"
        metadata = {
            "promotionItemId": item_id,
            "sourceRecordId": source_record_id,
            "scope": "global",
        }
        self._ensure_contract("promoted", metadata)
        frontmatter = yaml.dump(
            metadata,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        file_path.write_text(f"---\n{frontmatter}\n---\n\n{content}\n")
        return file_path

    def promoted_entry_exists(self, item_id: str) -> bool:
        file_path = self.promoted_entries_dir / "promoted" / f"{item_id}.md"
        return file_path.exists()

    def count_promoted_entries(self) -> int:
        promoted_dir = self.promoted_entries_dir / "promoted"
        if not promoted_dir.exists():
            return 0
        return len(list(promoted_dir.glob("*.md")))

    def list_promoted_entries(self) -> list[dict[str, str]]:
        promoted_dir = self.promoted_entries_dir / "promoted"
        if not promoted_dir.exists():
            return []

        items: list[dict[str, str]] = []
        for file_path in sorted(promoted_dir.glob("*.md")):
            raw = file_path.read_text()
            metadata = self._parse_frontmatter_metadata(raw)
            if metadata is None:
                continue

            item_id = str(metadata.get("promotionItemId", file_path.stem))
            source_record_id = str(metadata.get("sourceRecordId", ""))
            scope = str(metadata.get("scope", "global"))
            items.append(
                {
                    "itemId": item_id,
                    "sourceRecordId": source_record_id,
                    "scope": scope,
                    "path": str(file_path),
                }
            )

        return items

    def list_indexable_documents(self) -> list[dict[str, str]]:
        """Return indexable markdown documents with checksum and inferred record_type."""
        docs: list[dict[str, str]] = []

        if self.entries_dir.exists():
            for date_dir in sorted(self.entries_dir.iterdir()):
                if not date_dir.is_dir():
                    continue
                if date_dir.name in _FRAMEWORK_DIRS:
                    continue
                for md_file in sorted(date_dir.glob("*.md")):
                    docs.append(self._index_doc_info(md_file, record_type="entry"))

        if self.convo_entries_dir.exists():
            for md_file in sorted(self.convo_entries_dir.glob("*/*.md")):
                docs.append(self._index_doc_info(md_file, record_type="convo"))

        if self.collab_entries_dir.exists():
            for md_file in sorted(self.collab_entries_dir.glob("*/*.md")):
                docs.append(self._index_doc_info(md_file, record_type="collab"))

        promoted_dir = self.promoted_entries_dir / "promoted"
        if promoted_dir.exists():
            for md_file in sorted(promoted_dir.glob("*.md")):
                docs.append(self._index_doc_info(md_file, record_type="promoted"))

        return docs

    def _find_collab_file(self, record_id: str) -> tuple[CollabRecord, Path, str] | None:
        best: tuple[CollabRecord, Path, str] | None = None
        for file_path in self._iter_collab_files():
            loaded = self._load_collab_file(file_path)
            if loaded is None:
                continue
            record, body = loaded
            if record.record_id == record_id:
                if best is None or record.version > best[0].version:
                    best = (record, file_path, body)
        return best

    def _iter_collab_files(self) -> Iterator[Path]:
        if not self.collab_entries_dir.exists():
            return iter(())
        return iter(sorted(self.collab_entries_dir.glob("*/*.md")))

    @staticmethod
    def _load_collab_file(file_path: Path) -> tuple[CollabRecord, str] | None:
        raw = file_path.read_text()
        parsed = Storage._parse_collab_frontmatter(raw)
        if parsed is None:
            return None

        parts = raw.split("---\n", 2)
        body = parts[2].lstrip("\n") if len(parts) >= 3 else ""
        return parsed, body

    @staticmethod
    def _parse_frontmatter_metadata(raw: str) -> dict[str, object] | None:
        if not raw.startswith("---\n"):
            return None
        parts = raw.split("---\n", 2)
        if len(parts) < 3:
            return None
        return yaml.safe_load(parts[1]) or {}

    @staticmethod
    def _parse_collab_frontmatter(raw: str) -> CollabRecord | None:
        metadata = Storage._parse_frontmatter_metadata(raw)
        if metadata is None:
            return None
        try:
            return CollabRecord.model_validate(metadata)
        except Exception:
            return None

    @staticmethod
    def _render_collab_body(record: CollabRecord) -> str:
        body_lines = [record.summary, "", "## Evidence"]
        body_lines.extend([f"- {item}" for item in record.evidence])
        body_lines.append("")
        body_lines.append("## Next Action")
        body_lines.extend([f"- {item}" for item in record.next_action])
        return "\n".join(body_lines)

    @staticmethod
    def _ensure_contract(record_type: str, metadata: dict[str, object]) -> None:
        ok, reason = validate_document_contract(record_type, metadata)
        if not ok:
            raise ValueError(f"invalid {record_type} contract: {reason}")

    def _collab_path(self, record: CollabRecord) -> Path:
        day = record.created_at.date().isoformat()
        safe_task = re.sub(r'[^a-zA-Z0-9_-]', '-', record.task_id)
        return self.collab_entries_dir / day / f"{safe_task}-{record.status}-{record.record_id}.md"

    def _index_doc_info(self, file_path: Path, *, record_type: str) -> dict[str, str]:
        rel = file_path.relative_to(self.data_dir).as_posix()
        return {
            "doc_id": rel,
            "path": rel,
            "record_type": record_type,
            "checksum": self._sha256(file_path),
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return f"sha256:{digest}"
