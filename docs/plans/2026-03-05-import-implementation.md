# Import Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** LLM이 외부 마크다운 디렉토리를 분석하고 btwin-service에 임포트할 수 있도록, MCP 도구 1개 추가 + Storage 병합 동작 수정 + `/btwin-import` 스킬 작성.

**Architecture:** (1) `Storage.save_entry()` 충돌 시 병합 동작으로 변경. (2) `btwin_import_entry` MCP 도구 추가 (date/slug/tags를 직접 지정 가능). (3) `/btwin-import` 스킬이 LLM에게 파일 분석 → 도구 호출 워크플로우를 안내.

**Tech Stack:** Python, existing Storage/VectorStore/BTwin modules, FastMCP, Claude Code Skill (SKILL.md)

---

### Task 1: Storage.save_entry() merge-on-collision

같은 date/slug Entry가 이미 존재하면 덮어쓰기 대신 내용을 병합한다.

**Files:**
- Modify: `src/btwin/core/storage.py:15-28`
- Test: `tests/test_core/test_storage.py`

**Step 1: Write the failing tests**

In `tests/test_core/test_storage.py`, append:

```python
def test_save_entry_merges_on_collision(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry1 = Entry(
        date="2026-03-02",
        slug="merge-test",
        content="# First\n\nFirst content.",
        metadata={"tags": ["alpha"]},
    )
    entry2 = Entry(
        date="2026-03-02",
        slug="merge-test",
        content="Second content.",
        metadata={"tags": ["beta"]},
    )
    storage.save_entry(entry1)
    storage.save_entry(entry2)

    loaded = storage.read_entry("2026-03-02", "merge-test")
    assert loaded is not None
    assert "First content." in loaded.content
    assert "Second content." in loaded.content
    assert "---" in loaded.content
    assert set(loaded.metadata["tags"]) == {"alpha", "beta"}


def test_save_entry_merges_tags_union(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry1 = Entry(
        date="2026-03-02",
        slug="tag-merge",
        content="Content A",
        metadata={"tags": ["a", "b"]},
    )
    entry2 = Entry(
        date="2026-03-02",
        slug="tag-merge",
        content="Content B",
        metadata={"tags": ["b", "c"]},
    )
    storage.save_entry(entry1)
    storage.save_entry(entry2)

    loaded = storage.read_entry("2026-03-02", "tag-merge")
    assert set(loaded.metadata["tags"]) == {"a", "b", "c"}


def test_save_entry_no_collision_works_as_before(tmp_path):
    storage = Storage(data_dir=tmp_path)
    entry = Entry(
        date="2026-03-02",
        slug="no-collision",
        content="# New\n\nBrand new entry.",
        metadata={"topic": "test"},
    )
    saved_path = storage.save_entry(entry)
    assert saved_path.exists()
    loaded = storage.read_entry("2026-03-02", "no-collision")
    assert loaded.content == "# New\n\nBrand new entry."
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_core/test_storage.py::test_save_entry_merges_on_collision tests/test_core/test_storage.py::test_save_entry_merges_tags_union -v`
Expected: FAIL

**Step 3: Implement merge logic in save_entry()**

Replace the `save_entry` method in `src/btwin/core/storage.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_core/test_storage.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/btwin/core/storage.py tests/test_core/test_storage.py
git commit -m "feat(storage): merge content on save_entry collision instead of overwrite"
```

---

### Task 2: BTwin.import_entry() method + MCP tool

`date`, `slug`, `tags`를 직접 지정할 수 있는 임포트 전용 메서드와 MCP 도구 추가.

**Files:**
- Modify: `src/btwin/core/btwin.py`
- Modify: `src/btwin/mcp/server.py`
- Modify: `tests/test_core/test_btwin.py`
- Modify: `tests/test_mcp/test_server.py`

**Step 1: Write the failing tests for BTwin.import_entry()**

In `tests/test_core/test_btwin.py`, append:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_core/test_btwin.py::test_import_entry -v`
Expected: FAIL — `import_entry` method does not exist.

**Step 3: Implement BTwin.import_entry()**

In `src/btwin/core/btwin.py`, add method to `BTwin` class:

```python
def import_entry(
    self,
    content: str,
    date: str,
    slug: str,
    tags: list[str] | None = None,
    source_path: str | None = None,
) -> dict:
    """Import a single entry with explicit date, slug, and tags."""
    metadata: dict[str, object] = {}
    if tags:
        metadata["tags"] = tags
    if source_path:
        metadata["source_path"] = source_path
    metadata["imported_at"] = datetime.now(timezone.utc).isoformat()

    entry = Entry(
        date=date,
        slug=slug,
        content=content,
        metadata=metadata,
    )
    self.storage.save_entry(entry)

    doc_id = f"{date}/{slug}"
    self.vector_store.add(
        doc_id=doc_id,
        content=content,
        metadata={"date": date, "slug": slug},
    )

    try:
        self._update_summary(date, slug, content)
    except Exception:
        logger.warning("Failed to update summary for %s/%s", date, slug)

    return {"date": date, "slug": slug, "path": str(self.storage.entries_dir / date / f"{slug}.md")}
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_core/test_btwin.py -v`
Expected: ALL PASS

**Step 5: Write the failing test for MCP tool**

In `tests/test_mcp/test_server.py`, append (follow existing mock pattern in that file):

```python
@patch("btwin.mcp.server._get_twin")
def test_btwin_import_entry(mock_get_twin):
    mock = _mock_twin()
    mock.import_entry.return_value = {
        "date": "2026-02-24",
        "slug": "ea-report",
        "path": "/fake/entries/2026-02-24/ea-report.md",
    }
    mock_get_twin.return_value = mock
    result = btwin_import_entry(
        content="# Report",
        date="2026-02-24",
        slug="ea-report",
        tags="jobs,ea-korea",
    )
    assert "2026-02-24/ea-report" in result
    mock.import_entry.assert_called_once()
```

Also add the import at the top of the test file:

```python
from btwin.mcp.server import btwin_import_entry
```

**Step 6: Implement MCP tool**

In `src/btwin/mcp/server.py`, add before the `main()` function:

```python
@mcp.tool()
def btwin_import_entry(
    content: str,
    date: str,
    slug: str,
    tags: str | None = None,
    source_path: str | None = None,
) -> str:
    """Import a single entry with explicit date, slug, and tags.

    Use this when importing entries from external sources where you need
    to specify the exact date, slug, and tags instead of auto-generating them.

    Args:
        content: The markdown content of the entry
        date: Date in YYYY-MM-DD format (e.g., "2026-02-24")
        slug: Filename slug (e.g., "ea-interview-review")
        tags: Comma-separated tags (e.g., "jobs,ea-korea,interview")
        source_path: Original file path for dedup tracking
    """
    twin = _get_twin()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    result = twin.import_entry(
        content=content,
        date=date,
        slug=slug,
        tags=tag_list,
        source_path=source_path,
    )
    return f"Imported: {result['date']}/{result['slug']} → {result['path']}"
```

**Step 7: Run all tests**

Run: `uv run pytest -v`
Expected: ALL PASS

**Step 8: Commit**

```bash
git add src/btwin/core/btwin.py src/btwin/mcp/server.py tests/test_core/test_btwin.py tests/test_mcp/test_server.py
git commit -m "feat: add btwin_import_entry MCP tool with explicit date/slug/tags"
```

---

### Task 3: `/btwin-import` Skill

LLM이 외부 마크다운 디렉토리를 분석하고 `btwin_import_entry` 도구로 임포트하는 워크플로우를 정의하는 스킬.

**Files:**
- Create: `src/btwin/skills/btwin-import/SKILL.md`

**Step 1: Create the skill file**

Create `src/btwin/skills/btwin-import/SKILL.md`:

```markdown
---
name: btwin-import
description: Use when the user wants to import markdown files from an external directory into B-TWIN. Handles analysis, date/tag extraction, and batch import using LLM judgment.
---

# B-TWIN Import

외부 마크다운 디렉토리의 파일들을 분석하여 B-TWIN에 임포트합니다.
LLM이 각 파일의 내용을 읽고, 날짜/slug/tags를 판단하여 `btwin_import_entry` 도구로 저장합니다.

## When to Use

- 사용자가 "임포트해줘", "이 폴더 데이터 가져와" 등을 요청할 때
- `/btwin-import` 실행 시
- 외부 마크다운 프로젝트의 데이터를 B-TWIN으로 마이그레이션할 때

## Workflow

1. **소스 디렉토리 스캔** — Glob 도구로 `.md` 파일 목록 수집
2. **파일별 분석** — 각 파일을 Read로 읽고 내용 분석
3. **임포트 계획 제시** — 사용자에게 어떤 파일을 어떻게 임포트할지 보여주고 확인
4. **도구 호출** — `btwin_import_entry`로 각 Entry 저장
5. **결과 보고** — 임포트된 항목 수와 요약 출력

## Step 1: 파일 스캔

Glob 도구로 소스 디렉토리의 `.md` 파일을 수집한다.

**제외 대상:**
- 도트 디렉토리 하위 파일 (`.git/`, `.claude/`, `.venv/` 등)
- `node_modules/` 하위
- 이미 btwin 포맷인 `entries/` 하위

## Step 2: 파일 분석

각 `.md` 파일을 Read 도구로 읽고, 다음을 판단한다:

### 멀티섹션 감지

파일 안에 날짜 기반 헤딩(`### 260226`, `## 2026-02-26` 등)이 2개 이상이면, 각 섹션을 독립 Entry로 분리한다. 파일 제목 등 헤딩 이전 내용은 각 Entry의 prefix로 포함한다.

### 날짜 결정 (우선순위)

1. 파일 내용의 날짜 헤딩 (멀티섹션의 경우)
2. 파일명의 날짜 패턴 (YYMMDD, YYYY-MM-DD 등)
3. 파일 내용에서 날짜 맥락 추론
4. 확인 불가 시 사용자에게 질문

출력 형식: **반드시 `YYYY-MM-DD`** (예: `2026-02-24`)

### Slug 결정

파일의 핵심 주제를 반영하는 **영문 kebab-case** slug를 생성한다.
- 내용을 읽고 의미 있는 이름을 만든다
- 예: 면접 후기 → `ea-interview-review`, TA 로드맵 → `ta-career-roadmap`
- 2~4단어, 영문 소문자, 하이픈 구분

### Tags 결정

파일의 **내용을 기반으로** 의미 있는 태그를 생성한다.
- 폴더 경로는 참고만 하고, 내용에서 주제를 추출한다
- 예: 면접 리포트 → `[interview, ea-korea, job-prep]`
- 태그는 영문 소문자 kebab-case
- 3~5개 정도가 적절

## Step 3: 임포트 계획 제시

분석 결과를 사용자에게 테이블로 보여주고 확인을 받는다:

```
| # | 원본 파일 | → Entry | date | slug | tags |
|---|-----------|---------|------|------|------|
| 1 | library/smalltalk.md (섹션 260226) | 2026-02-26/smalltalk-career | 2026-02-26 | smalltalk-career | career, ea-korea |
| 2 | jobs/AdeccoKorea/00_report_260224.md | 2026-02-24/ea-jd-analysis | 2026-02-24 | ea-jd-analysis | interview, ea-korea, job-prep |
| ... | ... | ... | ... | ... | ... |
```

**반드시 사용자 확인 후 진행한다.**

## Step 4: 도구 호출

확인이 되면 각 Entry에 대해 `btwin_import_entry`를 호출한다:

- `content`: 마크다운 본문 (원본 그대로)
- `date`: YYYY-MM-DD
- `slug`: 판단한 slug
- `tags`: 쉼표 구분 태그 문자열
- `source_path`: 원본 파일의 절대 경로 (중복 임포트 방지용)

## Step 5: 결과 보고

임포트 완료 후 요약을 출력한다:
- 임포트된 Entry 수
- 스킵된 파일 (비-마크다운 등)
- `btwin_search`로 검색 가능 여부 확인 안내

## Rules

- **내용을 반드시 읽고 판단한다** — 파일명이나 폴더 구조만으로 추측하지 않는다
- **원본 내용은 수정하지 않는다** — content는 원본 마크다운 그대로 저장
- **사용자 확인 필수** — 임포트 계획을 보여주고 승인 후 실행
- **한 번에 하나씩** — 파일이 많으면 배치로 나눠서 진행 (10개 단위)
- **date 형식은 YYYY-MM-DD** — 반드시 이 형식으로 통일
- **언어**: 한국어로 안내
```

**Step 2: Ensure skills directory exists**

```bash
mkdir -p src/btwin/skills/btwin-import
```

**Step 3: Commit**

```bash
git add src/btwin/skills/btwin-import/SKILL.md
git commit -m "feat: add /btwin-import skill for LLM-driven markdown import"
```

---

### Task 4: End-to-end verification

실제 b-twin 데이터로 스킬 + MCP 도구가 동작하는지 검증한다.

**Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

**Step 2: Manual verification**

MCP 서버를 실행하고, Claude Code에서 `/btwin-import`를 실행하여 `/Users/home/playground/b-twin` 디렉토리를 임포트한다.

검증 항목:
- Claude가 `.md` 파일들을 읽고 날짜/slug/tags를 올바르게 판단하는지
- `btwin_import_entry` 호출이 정상적으로 동작하는지
- `btwin_search "아데코 면접"`으로 검색이 되는지
- 같은 디렉토리를 다시 임포트하면 내용이 병합되는지
