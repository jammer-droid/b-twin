"""B-TWIN core integration class."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from btwin.config import BTwinConfig
from btwin.core.llm import LLMClient
from btwin.core.models import Entry
from btwin.core.session import SessionManager
from btwin.core.storage import Storage
from btwin.core.vector import VectorStore

logger = logging.getLogger(__name__)


class BTwin:
    def __init__(self, config: BTwinConfig) -> None:
        self.config = config
        self.storage = Storage(data_dir=config.data_dir)
        self.vector_store = VectorStore(persist_dir=config.data_dir / "index")
        self.session_manager = SessionManager()

        # LLM is optional — only needed for CLI standalone mode
        self._llm: LLMClient | None = None
        if config.llm.api_key:
            self._llm = LLMClient(config.llm)

    def start_session(self, topic: str | None = None) -> dict:
        """Start a new session with an optional topic."""
        session = self.session_manager.start_session(topic=topic)
        return {
            "active": True,
            "topic": session.topic,
            "created_at": session.created_at.isoformat(),
        }

    def end_session(
        self,
        summary: str | None = None,
        slug: str | None = None,
    ) -> dict | None:
        """End the current session and save as an entry.

        Args:
            summary: Session summary text. If not provided, uses LLM (requires API key)
                     or falls back to raw message log.
            slug: Filename slug. If not provided, uses LLM or defaults to topic/timestamp.
        """
        session = self.session_manager.current_session
        if session is None:
            return None

        # Generate summary if not provided
        if summary is None:
            conversation = session.to_llm_messages()
            if self._llm:
                try:
                    summary = self._llm.summarize(conversation)
                except Exception:
                    logger.warning("LLM summarize failed, using raw messages")
                    summary = self._raw_summary(session)
            else:
                summary = self._raw_summary(session)

        # Generate slug if not provided
        if slug is None:
            if self._llm:
                try:
                    conversation = session.to_llm_messages()
                    slug = self._llm.generate_slug(conversation)
                except Exception:
                    slug = self._fallback_slug(session)
            else:
                slug = self._fallback_slug(session)

        self.session_manager.end_session()
        now = datetime.now(timezone.utc)
        date = now.strftime("%Y-%m-%d")

        title = slug.replace("-", " ").title()
        content = f"# {title}\n\n{summary}"

        entry = Entry(
            date=date,
            slug=slug,
            content=content,
            metadata={
                "topic": session.topic or "",
                "created_at": now.isoformat(),
            },
        )
        self.storage.save_entry(entry)

        doc_id = f"{date}/{slug}"
        self.vector_store.add(
            doc_id=doc_id,
            content=content,
            metadata={"date": date, "slug": slug, "topic": session.topic or ""},
        )

        try:
            self._update_summary(date, slug, content)
        except Exception:
            logger.warning("Failed to update summary.md", exc_info=True)
        return {"date": date, "slug": slug, "summary": summary}

    def chat(self, message: str) -> str:
        """Send a message and get a response. Requires LLM API key."""
        if not self._llm:
            raise RuntimeError("LLM API key required for chat. Use MCP client instead.")

        self.session_manager.add_message("user", message)

        context = []
        search_results = self.vector_store.search(message, n_results=3)
        for result in search_results:
            context.append(result["content"])

        conversation = self.session_manager.get_conversation()
        response = self._llm.chat(conversation, context=context if context else None)

        self.session_manager.add_message("assistant", response)
        return response

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Search past entries by semantic similarity."""
        return self.vector_store.search(query, n_results=n_results)

    def record(self, content: str, topic: str | None = None) -> dict:
        """Manually record a note."""
        now = datetime.now(timezone.utc)
        date = now.strftime("%Y-%m-%d")
        base_slug = topic or "note"
        slug = f"{base_slug}-{now.strftime('%H%M%S%f')}"

        entry = Entry(
            date=date,
            slug=slug,
            content=content,
            metadata={
                "topic": topic or "",
                "created_at": now.isoformat(),
            },
        )
        saved_path = self.storage.save_entry(entry)

        doc_id = f"{date}/{slug}"
        self.vector_store.add(
            doc_id=doc_id,
            content=content,
            metadata={"date": date, "slug": slug},
        )

        try:
            self._update_summary(date, slug, content)
        except Exception:
            logger.warning("Failed to update summary.md", exc_info=True)
        return {"date": date, "slug": slug, "path": str(saved_path)}

    def session_status(self) -> dict:
        """Get the current session status."""
        session = self.session_manager.current_session
        if session is None:
            return {"active": False}
        return {
            "active": True,
            "topic": session.topic,
            "message_count": len(session.messages),
            "created_at": session.created_at.isoformat(),
        }

    def _update_summary(self, date: str, slug: str, content: str) -> None:
        """Append an entry summary to the cumulative summary.md file."""
        summary_path = self.config.data_dir / "summary.md"

        # Extract first line of content as preview (strip markdown heading)
        preview = content.strip().split("\n")[0].lstrip("# ").strip()
        if len(preview) > 80:
            preview = preview[:77] + "..."

        new_line = f"- **{slug}**: {preview}"

        if summary_path.exists():
            existing = summary_path.read_text()
        else:
            existing = "# B-TWIN Summary\n"

        # Check if today's date section exists
        date_header = f"## {date}"
        if date_header in existing:
            # Insert new line after the date header
            parts = existing.split(date_header, 1)
            parts[1] = f"\n\n{new_line}" + parts[1]
            updated = date_header.join(parts)
        else:
            # Add new date section after the title
            header_end = existing.index("\n") + 1
            date_section = f"\n{date_header}\n\n{new_line}\n\n---\n"
            updated = existing[:header_end] + date_section + existing[header_end:]

        summary_path.write_text(updated)

    @staticmethod
    def _raw_summary(session) -> str:
        return "\n".join(f"- {m.content[:80]}" for m in session.messages)

    @staticmethod
    def _fallback_slug(session) -> str:
        if session.topic:
            return session.topic
        now = datetime.now(timezone.utc)
        return f"session-{now.strftime('%H%M%S')}"
