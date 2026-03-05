from unittest.mock import patch, MagicMock
from pathlib import Path

from btwin.core.btwin import BTwin
from btwin.config import BTwinConfig


def make_btwin(tmp_path, with_llm=False):
    """Create BTwin with optional LLM mock."""
    config = BTwinConfig(data_dir=tmp_path)
    if with_llm:
        with patch("btwin.core.btwin.LLMClient") as MockLLM:
            mock_llm = MockLLM.return_value
            mock_llm.chat.return_value = "Hello! Nice to meet you."
            mock_llm.summarize.return_value = "- Discussed greeting"
            mock_llm.generate_slug.return_value = "greeting-test"
            # Set api_key so LLM gets initialized
            config.llm.api_key = "test-key"
            twin = BTwin(config)
            return twin, mock_llm
    twin = BTwin(config)
    return twin, None


# --- start_session ---

def test_start_session(tmp_path):
    twin, _ = make_btwin(tmp_path)
    result = twin.start_session(topic="unreal-study")
    assert result["active"] is True
    assert result["topic"] == "unreal-study"
    assert twin.session_manager.has_active_session()


def test_start_session_no_topic(tmp_path):
    twin, _ = make_btwin(tmp_path)
    result = twin.start_session()
    assert result["active"] is True
    assert result["topic"] is None


# --- end_session with summary provided (MCP mode, no LLM) ---

def test_end_session_with_summary(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.start_session(topic="test-topic")
    twin.session_manager.add_message("user", "Hello")
    result = twin.end_session(summary="User said hello", slug="hello-test")
    assert result is not None
    assert result["slug"] == "hello-test"
    assert result["summary"] == "User said hello"
    entries = twin.storage.list_entries()
    assert len(entries) == 1
    assert twin.vector_store.count() == 1


def test_end_session_with_summary_no_slug(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.start_session(topic="shader-study")
    twin.session_manager.add_message("user", "Learned shaders")
    result = twin.end_session(summary="Studied shaders today")
    assert result is not None
    # slug should fall back to topic
    assert result["slug"] == "shader-study"


def test_end_session_no_active(tmp_path):
    twin, _ = make_btwin(tmp_path)
    result = twin.end_session(summary="test")
    assert result is None


def test_end_session_fallback_raw_summary(tmp_path):
    """No summary, no LLM → raw message log."""
    twin, _ = make_btwin(tmp_path)
    twin.start_session(topic="test")
    twin.session_manager.add_message("user", "Hello world")
    result = twin.end_session()
    assert result is not None
    assert "Hello world" in result["summary"]


# --- end_session with LLM (CLI mode) ---

def test_end_session_with_llm(tmp_path):
    twin, mock_llm = make_btwin(tmp_path, with_llm=True)
    twin.start_session()
    twin.session_manager.add_message("user", "Hello")
    result = twin.end_session()
    assert result is not None
    assert result["summary"] == "- Discussed greeting"
    assert result["slug"] == "greeting-test"


def test_end_session_llm_failure(tmp_path):
    twin, mock_llm = make_btwin(tmp_path, with_llm=True)
    twin.start_session()
    twin.session_manager.add_message("user", "Hello")
    mock_llm.summarize.side_effect = RuntimeError("API error")
    result = twin.end_session()
    assert result is not None
    assert "Hello" in result["summary"]  # raw fallback


# --- search ---

def test_search(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.vector_store.add(
        doc_id="test-1",
        content="Studied Unreal Material Editor",
        metadata={"date": "2026-03-02", "slug": "unreal-study"},
    )
    results = twin.search("Unreal")
    assert len(results) >= 1


# --- record ---

def test_record(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.record("Manual note about TA career", topic="career-ta")
    entries = twin.storage.list_entries()
    assert len(entries) == 1
    assert twin.vector_store.count() == 1
    assert entries[0].slug.startswith("career-ta-")


def test_record_no_collision(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.record("Note one", topic="test")
    twin.record("Note two", topic="test")
    entries = twin.storage.list_entries()
    assert len(entries) >= 1
    assert twin.vector_store.count() == 2


def test_record_convo(tmp_path):
    twin, _ = make_btwin(tmp_path)
    result = twin.record_convo("기억해줘", requested_by_user=True, topic="memory")

    assert "convo" in result["path"]
    convo_entries = twin.storage.list_convo_entries()
    assert len(convo_entries) == 1
    assert convo_entries[0].metadata.get("recordType") == "convo"
    assert twin.vector_store.count() == 1


# --- summary.md ---

def test_end_session_updates_summary(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.start_session(topic="test-topic")
    twin.session_manager.add_message("user", "Hello")
    twin.end_session(summary="User said hello", slug="hello-test")
    summary_path = tmp_path / "summary.md"
    assert summary_path.exists()
    content = summary_path.read_text()
    assert "hello-test" in content
    # Preview is extracted from the first line of content (the title)
    assert "Hello Test" in content


def test_record_updates_summary(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.record("Manual note about TA career", topic="career-ta")
    summary_path = tmp_path / "summary.md"
    assert summary_path.exists()
    content = summary_path.read_text()
    assert "career-ta" in content
    assert "Manual note about TA career" in content


def test_summary_accumulates(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.record("First note", topic="first")
    twin.record("Second note", topic="second")
    summary_path = tmp_path / "summary.md"
    content = summary_path.read_text()
    assert "first" in content
    assert "second" in content
    # Newest entry appears first (closer to top)
    assert content.index("second") < content.index("first")


# --- session_status ---

def test_session_status_no_session(tmp_path):
    twin, _ = make_btwin(tmp_path)
    status = twin.session_status()
    assert status["active"] is False


def test_session_status_with_session(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.start_session(topic="test")
    twin.session_manager.add_message("user", "Hello")
    status = twin.session_status()
    assert status["active"] is True
    assert status["message_count"] == 1


# --- chat (requires LLM) ---

def test_chat_requires_llm(tmp_path):
    twin, _ = make_btwin(tmp_path)
    import pytest
    with pytest.raises(RuntimeError, match="LLM API key required"):
        twin.chat("Hello")


def test_chat_with_llm(tmp_path):
    twin, mock_llm = make_btwin(tmp_path, with_llm=True)
    response = twin.chat("Hello")
    assert response == "Hello! Nice to meet you."
    assert twin.session_manager.has_active_session()


# --- import_entry ---

def test_import_entry(tmp_path):
    twin, _ = make_btwin(tmp_path)
    result = twin.import_entry(
        content="# EA Report\n\nAnalysis.",
        date="2026-02-24",
        slug="ea-report",
        tags=["jobs", "ea-korea"],
        source_path="/fake/report.md",
    )
    assert result["date"] == "2026-02-24"
    assert result["slug"] == "ea-report"
    entries = twin.storage.list_entries()
    assert len(entries) == 1
    assert entries[0].metadata["tags"] == ["jobs", "ea-korea"]
    assert entries[0].metadata["source_path"] == "/fake/report.md"
    assert twin.vector_store.count() == 1


def test_import_entry_minimal(tmp_path):
    twin, _ = make_btwin(tmp_path)
    result = twin.import_entry(
        content="Just a note.",
        date="2026-02-24",
        slug="note",
    )
    assert result["date"] == "2026-02-24"
    assert result["slug"] == "note"
