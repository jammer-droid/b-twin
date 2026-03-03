# Entries Resource & Summary Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add individual entry MCP resource and cumulative summary.md auto-generation

**Architecture:** (1) Add `btwin://entries/{date}/{slug}` resource template to MCP server using existing `storage.read_entry()`. (2) Add `_update_summary()` method to BTwin that appends new entry summaries to `~/.btwin/summary.md` on every `end_session()` and `record()` call.

**Tech Stack:** Python, FastMCP (resource templates), existing Storage module

---

### Task 1: Add `btwin://entries/{date}/{slug}` MCP Resource

**Files:**
- Modify: `src/btwin/mcp/server.py:125-135`
- Test: `tests/test_mcp/test_server.py`

**Step 1: Write the failing test**

In `tests/test_mcp/test_server.py`, add:

```python
from btwin.mcp.server import read_entry

@patch("btwin.mcp.server._get_twin")
def test_read_entry_found(mock_get_twin):
    mock = _mock_twin()
    mock.storage.read_entry.return_value = MagicMock(
        date="2026-03-02", slug="test-entry", content="# Test Entry\n\nSome content"
    )
    mock_get_twin.return_value = mock
    result = read_entry("2026-03-02", "test-entry")
    assert "Test Entry" in result
    assert "Some content" in result


@patch("btwin.mcp.server._get_twin")
def test_read_entry_not_found(mock_get_twin):
    mock = _mock_twin()
    mock.storage.read_entry.return_value = None
    mock_get_twin.return_value = mock
    result = read_entry("2026-03-02", "nonexistent")
    assert "not found" in result.lower()
```

Also update the import at the top of the file to include `read_entry`:

```python
from btwin.mcp.server import (
    mcp,
    btwin_start_session,
    btwin_end_session,
    btwin_search,
    btwin_record,
    btwin_session_status,
    read_entry,
)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/home/playground/btwin-service && uv run pytest tests/test_mcp/test_server.py::test_read_entry_found tests/test_mcp/test_server.py::test_read_entry_not_found -v`
Expected: FAIL with ImportError (read_entry doesn't exist)

**Step 3: Write minimal implementation**

In `src/btwin/mcp/server.py`, add after the `list_entries` resource (after line 135):

```python
@mcp.resource("btwin://entries/{date}/{slug}")
def read_entry(date: str, slug: str) -> str:
    """Read a specific entry by date and slug."""
    twin = _get_twin()
    entry = twin.storage.read_entry(date, slug)
    if entry is None:
        return f"Entry not found: {date}/{slug}"
    return entry.content
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/home/playground/btwin-service && uv run pytest tests/test_mcp/test_server.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
cd /Users/home/playground/btwin-service
git add src/btwin/mcp/server.py tests/test_mcp/test_server.py
git commit -m "feat: add btwin://entries/{date}/{slug} resource for individual entry access"
```

---

### Task 2: Add cumulative summary.md generation

When `end_session()` or `record()` saves an entry, also append a summary line to `~/.btwin/summary.md`. The summary file accumulates entries with newest at top, grouped by date.

**Format of `summary.md`:**

```markdown
# B-TWIN Summary

## 2026-03-02

- **career-ta-discussion**: TA 전직 관련 논의
- **unreal-study-143022**: Unreal 셰이더 공부 기록

---

## 2026-03-01

- **greeting-test**: 인사 테스트

---
```

**Files:**
- Modify: `src/btwin/core/btwin.py:78-93` (end_session), `src/btwin/core/btwin.py:117-134` (record)
- Test: `tests/test_core/test_btwin.py`

**Step 1: Write the failing tests**

In `tests/test_core/test_btwin.py`, add:

```python
def test_end_session_updates_summary(tmp_path):
    twin, _ = make_btwin(tmp_path)
    twin.start_session(topic="test-topic")
    twin.session_manager.add_message("user", "Hello")
    twin.end_session(summary="User said hello", slug="hello-test")
    summary_path = tmp_path / "summary.md"
    assert summary_path.exists()
    content = summary_path.read_text()
    assert "hello-test" in content
    assert "User said hello" in content


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
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/home/playground/btwin-service && uv run pytest tests/test_core/test_btwin.py::test_end_session_updates_summary tests/test_core/test_btwin.py::test_record_updates_summary tests/test_core/test_btwin.py::test_summary_accumulates -v`
Expected: FAIL (summary.md not created)

**Step 3: Write minimal implementation**

In `src/btwin/core/btwin.py`, add the `_update_summary` method to the `BTwin` class:

```python
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
        parts = existing.split(date_header)
        parts[1] = f"\n\n{new_line}" + parts[1]
        updated = date_header.join(parts)
    else:
        # Add new date section after the title
        header_end = existing.index("\n") + 1
        date_section = f"\n{date_header}\n\n{new_line}\n\n---\n"
        updated = existing[:header_end] + date_section + existing[header_end:]

    summary_path.write_text(updated)
```

Then call `_update_summary` at the end of `end_session()` (before the return statement):

```python
        self._update_summary(date, slug, content)

        return {"date": date, "slug": slug, "summary": summary}
```

And at the end of `record()` (before the return statement):

```python
        self._update_summary(date, slug, content)

        return {"date": date, "slug": slug, "path": str(saved_path)}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/home/playground/btwin-service && uv run pytest tests/test_core/test_btwin.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `cd /Users/home/playground/btwin-service && uv run pytest -v`
Expected: ALL PASS (54+ passed, 5 skipped)

**Step 6: Commit**

```bash
cd /Users/home/playground/btwin-service
git add src/btwin/core/btwin.py tests/test_core/test_btwin.py
git commit -m "feat: add cumulative summary.md generation on end_session and record"
```
