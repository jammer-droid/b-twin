"""Audit logging utilities for collab/promotion workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class AuditLogger:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceId": trace_id if trace_id else f"trc_{uuid4().hex[:12]}",
            "eventType": event_type,
            "payload": payload,
        }
        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def tail(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.file_path.exists() or limit <= 0:
            return []

        lines = _tail_lines(self.file_path, limit)
        return [json.loads(line) for line in lines if line.strip()]


def _tail_lines(path: Path, n: int, chunk_size: int = 8192) -> list[str]:
    """Read the last *n* lines from *path* without loading the entire file.

    Uses a reverse-seek strategy: read backward in *chunk_size* blocks
    until we have collected enough newline-delimited lines.
    """
    with path.open("rb") as f:
        f.seek(0, 2)  # seek to end
        file_size = f.tell()
        if file_size == 0:
            return []

        buf = b""
        position = file_size

        while position > 0:
            read_size = min(chunk_size, position)
            position -= read_size
            f.seek(position)
            buf = f.read(read_size) + buf
            # +1 because the last line may end with \n producing an empty split
            if buf.count(b"\n") >= n + 1:
                break

    text = buf.decode("utf-8")
    all_lines = text.splitlines()
    return all_lines[-n:]
