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

    def log(self, *, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceId": f"trc_{uuid4().hex[:12]}",
            "eventType": event_type,
            "payload": payload,
        }
        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def tail(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.file_path.exists() or limit <= 0:
            return []

        lines = self.file_path.read_text(encoding="utf-8").splitlines()
        selected = lines[-limit:]
        return [json.loads(line) for line in selected if line.strip()]
