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

_PROJECT_NAME_RE = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$")
_RESERVED_PROJECT_NAMES = {"global", "convo", "collab"}
_DEFAULT_PROJECT = "_global"
_RECORD_SUBDIRS = {"convo", "collab"}


class Storage:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.entries_dir = data_dir / "entries"
        self.promoted_entries_dir = self.entries_dir / "global"

    # -- helpers for project-aware paths --

    def _resolve_project(self, project: str | None) -> str:
        if project is None or project == "":
            return _DEFAULT_PROJECT
        if not _PROJECT_NAME_RE.match(project):
            raise ValueError(
                f"Invalid project name: {project!r}. "
                "Must match [a-zA-Z0-9_][a-zA-Z0-9_.-]*"
            )
        if project in _RESERVED_PROJECT_NAMES:
            raise ValueError(f"'{project}' is a reserved project name")
        return project

    def _project_dir(self, project: str | None) -> Path:
        return self.entries_dir / self._resolve_project(project)

    @property
    def convo_entries_dir(self) -> Path:
        """Legacy accessor -- points to _global/convo for backward compat."""
        return self._project_dir(None) / "convo"

    @property
    def collab_entries_dir(self) -> Path:
        """Legacy accessor -- points to _global/collab for backward compat."""
        return self._project_dir(None) / "collab"

    # =========================================================================
    # save / read / list entries
    # =========================================================================

    def save_entry(self, entry: Entry, *, project: str | None = None) -> Path:
        """Save an entry. If same date/slug exists, merge content and tags."""
        resolved = self._resolve_project(project)
        date_dir = self._project_dir(project) / entry.date
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
        fm["project"] = resolved
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

    def list_entries(self, *, project: str | None = None) -> list[Entry]:
        """List saved entries.

        If *project* is given, scan only ``entries/{project}/``.
        If *project* is None, scan all project directories.
        """
        if not self.entries_dir.exists():
            return []

        if project is not None:
            return self._list_entries_in_project(self._project_dir(project))

        # project=None  ->  scan every project directory
        entries: list[Entry] = []
        for proj_dir in sorted(self.entries_dir.iterdir()):
            if not proj_dir.is_dir():
                continue
            # "global" is for promoted entries, not regular project dir
            if proj_dir.name == "global":
                continue
            entries.extend(self._list_entries_in_project(proj_dir))
        return entries

    def _list_entries_in_project(self, proj_dir: Path) -> list[Entry]:
        """List regular entries inside a single project directory, skipping convo/collab."""
        entries: list[Entry] = []
        if not proj_dir.exists():
            return entries
        for date_dir in sorted(proj_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            if date_dir.name in _RECORD_SUBDIRS:
                continue
            for md_file in sorted(date_dir.glob("*.md")):
                raw = md_file.read_text()
                entries.append(self._parse_file(raw, date_dir.name, md_file.stem))
        return entries

    def read_entry(self, date: str, slug: str, *, project: str | None = None) -> Entry | None:
        """Read a specific entry by date and slug."""
        file_path = self._project_dir(project) / date / f"{slug}.md"
        if not file_path.exists():
            return None
        raw = file_path.read_text()
        return self._parse_file(raw, date, slug)

    # =========================================================================
    # convo records
    # =========================================================================

    def save_convo_record(
        self,
        *,
        content: str,
        requested_by_user: bool = False,
        topic: str | None = None,
        created_at: datetime | None = None,
        project: str | None = None,
    ) -> Entry:
        """Save explicit conversation memory under entries/{project}/convo/YYYY-MM-DD/."""
        resolved = self._resolve_project(project)
        now = created_at or datetime.now(timezone.utc)
        date = now.strftime("%Y-%m-%d")
        slug = f"convo-{now.strftime('%H%M%S%f')}"

        convo_dir = self._project_dir(project) / "convo"
        date_dir = convo_dir / date
        date_dir.mkdir(parents=True, exist_ok=True)
        file_path = date_dir / f"{slug}.md"

        metadata: dict[str, object] = {
            "date": date,
            "slug": slug,
            "recordType": "convo",
            "requestedByUser": requested_by_user,
            "created_at": now.isoformat(),
            "project": resolved,
        }
        if topic:
            metadata["topic"] = topic

        self._ensure_contract("convo", metadata)
        frontmatter = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()
        file_path.write_text(f"---\n{frontmatter}\n---\n\n{content}\n")
        return Entry(date=date, slug=slug, content=content, metadata=metadata)

    def list_convo_entries(self, *, project: str | None = None) -> list[Entry]:
        """List explicit convo records.

        If *project* is None, returns convo records from all projects (backward compat).
        """
        entries: list[Entry] = []

        if project is not None:
            convo_dir = self._project_dir(project) / "convo"
            return self._list_convo_in_dir(convo_dir)

        # Scan all projects
        if not self.entries_dir.exists():
            return entries
        for proj_dir in sorted(self.entries_dir.iterdir()):
            if not proj_dir.is_dir() or proj_dir.name == "global":
                continue
            convo_dir = proj_dir / "convo"
            entries.extend(self._list_convo_in_dir(convo_dir))
        return entries

    def _list_convo_in_dir(self, convo_dir: Path) -> list[Entry]:
        entries: list[Entry] = []
        if not convo_dir.exists():
            return entries
        for date_dir in sorted(convo_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            for md_file in sorted(date_dir.glob("*.md")):
                raw = md_file.read_text()
                entries.append(self._parse_file(raw, date_dir.name, md_file.stem))
        return entries

    # =========================================================================
    # collab records
    # =========================================================================

    def save_collab_record(self, record: CollabRecord, *, project: str | None = None) -> Path:
        """Save a collab record under entries/{project}/collab/YYYY-MM-DD/."""
        file_path = self._collab_path(record, project=project)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        metadata = record.model_dump(by_alias=True, mode="json")
        metadata["project"] = self._resolve_project(project)
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

    def read_collab_record(self, record_id: str, *, project: str | None = None) -> CollabRecord | None:
        """Read a collab record by record id."""
        loaded = self._find_collab_file(record_id, project=project)
        if loaded is None:
            return None
        return loaded[0]

    def read_collab_record_document(self, record_id: str, *, project: str | None = None) -> dict[str, str | dict[str, object]] | None:
        """Read collab record with frontmatter and markdown body."""
        loaded = self._find_collab_file(record_id, project=project)
        if loaded is None:
            return None

        record, file_path, body = loaded
        return {
            "recordId": record.record_id,
            "path": str(file_path),
            "frontmatter": record.model_dump(by_alias=True, mode="json"),
            "content": body,
        }

    def collab_index_doc_info(self, record_id: str, *, project: str | None = None) -> dict[str, str] | None:
        """Return indexable document info for a collab record id."""
        loaded = self._find_collab_file(record_id, project=project)
        if loaded is None:
            return None
        _record, file_path, _body = loaded
        return self._index_doc_info(file_path, record_type="collab")

    def update_collab_record(
        self,
        record_id: str,
        *,
        status: str,
        version: int,
        author_agent: str | None = None,
        project: str | None = None,
    ) -> CollabRecord | None:
        """Update status/version for an existing collab record."""
        loaded = self._find_collab_file(record_id, project=project)
        if loaded is None:
            return None

        existing, old_path, _body = loaded
        payload = existing.model_dump(by_alias=True, mode="json")
        payload["status"] = status
        payload["version"] = version
        if author_agent is not None:
            payload["authorAgent"] = author_agent

        updated = CollabRecord.model_validate(payload)
        new_path = self._collab_path(updated, project=project)
        self.save_collab_record(updated, project=project)
        if old_path != new_path and old_path.exists():
            old_path.unlink()
        return updated

    def list_collab_records(self, *, project: str | None = None) -> list[CollabRecord]:
        """List all collab records.

        If *project* is None, returns collab records from all projects (backward compat).
        """
        records: list[CollabRecord] = []
        for file_path in self._iter_collab_files(project=project):
            loaded = self._load_collab_file(file_path)
            if loaded is None:
                continue
            records.append(loaded[0])
        return records

    # =========================================================================
    # promoted entries (no project partitioning -- always global)
    # =========================================================================

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

    # =========================================================================
    # indexable documents
    # =========================================================================

    def list_indexable_documents(self, *, project: str | None = None) -> list[dict[str, str]]:
        """Return indexable markdown documents with checksum, record_type, and project.

        If *project* is given, returns only that project's docs.
        If *project* is None, returns docs from all projects.
        """
        docs: list[dict[str, str]] = []

        if not self.entries_dir.exists():
            return docs

        project_dirs = self._collect_project_dirs(project)

        for proj_name, proj_dir in project_dirs:
            # Regular entries: entries/{project}/{date}/*.md
            for date_dir in sorted(proj_dir.iterdir()):
                if not date_dir.is_dir():
                    continue
                if date_dir.name in _RECORD_SUBDIRS:
                    continue
                for md_file in sorted(date_dir.glob("*.md")):
                    info = self._index_doc_info(md_file, record_type="entry")
                    info["project"] = proj_name
                    docs.append(info)

            # Convo: entries/{project}/convo/{date}/*.md
            convo_dir = proj_dir / "convo"
            if convo_dir.exists():
                for md_file in sorted(convo_dir.glob("*/*.md")):
                    info = self._index_doc_info(md_file, record_type="convo")
                    info["project"] = proj_name
                    docs.append(info)

            # Collab: entries/{project}/collab/{date}/*.md
            collab_dir = proj_dir / "collab"
            if collab_dir.exists():
                for md_file in sorted(collab_dir.glob("*/*.md")):
                    info = self._index_doc_info(md_file, record_type="collab")
                    info["project"] = proj_name
                    docs.append(info)

        # Promoted entries are always global (not project-partitioned)
        if project is None:
            promoted_dir = self.promoted_entries_dir / "promoted"
            if promoted_dir.exists():
                for md_file in sorted(promoted_dir.glob("*.md")):
                    info = self._index_doc_info(md_file, record_type="promoted")
                    info["project"] = "_global"
                    docs.append(info)

        return docs

    def _collect_project_dirs(self, project: str | None) -> list[tuple[str, Path]]:
        """Return (project_name, project_dir) pairs to scan."""
        if project is not None:
            proj_dir = self._project_dir(project)
            if proj_dir.exists():
                return [(self._resolve_project(project), proj_dir)]
            return []

        result: list[tuple[str, Path]] = []
        if not self.entries_dir.exists():
            return result
        for d in sorted(self.entries_dir.iterdir()):
            if not d.is_dir():
                continue
            # "global" is for promoted entries -- skip
            if d.name == "global":
                continue
            result.append((d.name, d))
        return result

    # =========================================================================
    # collab internal helpers
    # =========================================================================

    def _find_collab_file(self, record_id: str, *, project: str | None = None) -> tuple[CollabRecord, Path, str] | None:
        best: tuple[CollabRecord, Path, str] | None = None
        for file_path in self._iter_collab_files(project=project):
            loaded = self._load_collab_file(file_path)
            if loaded is None:
                continue
            record, body = loaded
            if record.record_id == record_id:
                if best is None or record.version > best[0].version:
                    best = (record, file_path, body)
        return best

    def _iter_collab_files(self, *, project: str | None = None) -> Iterator[Path]:
        """Iterate over collab markdown files.

        If *project* is None, scan all project dirs for collab files (backward compat).
        """
        if project is not None:
            collab_dir = self._project_dir(project) / "collab"
            if not collab_dir.exists():
                return iter(())
            return iter(sorted(collab_dir.glob("*/*.md")))

        # Scan all projects
        files: list[Path] = []
        if not self.entries_dir.exists():
            return iter(files)
        for proj_dir in sorted(self.entries_dir.iterdir()):
            if not proj_dir.is_dir() or proj_dir.name == "global":
                continue
            collab_dir = proj_dir / "collab"
            if collab_dir.exists():
                files.extend(sorted(collab_dir.glob("*/*.md")))
        return iter(files)

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
        # Strip storage-level keys not part of CollabRecord (extra="forbid").
        metadata.pop("project", None)
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

    def _collab_path(self, record: CollabRecord, *, project: str | None = None) -> Path:
        day = record.created_at.date().isoformat()
        safe_task = re.sub(r'[^a-zA-Z0-9_-]', '-', record.task_id)
        collab_dir = self._project_dir(project) / "collab"
        return collab_dir / day / f"{safe_task}-{record.status}-{record.record_id}.md"

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
