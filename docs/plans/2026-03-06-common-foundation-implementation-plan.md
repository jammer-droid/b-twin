# Common Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the shared foundation needed by both workflow orchestration and record/dashboard features in B-TWIN.

**Architecture:** Reuse B-TWIN’s existing markdown/frontmatter storage, indexing, audit, and ops patterns. Add only the minimum shared schema, storage/index compatibility, API structure, and UI shell required so workflow and dashboard features can be built on a common base.

**Tech Stack:** Python, FastAPI, Typer, Pydantic, markdown/frontmatter storage, existing B-TWIN indexer/vector stack, pytest

---

### Task 1: Shared metadata/schema baseline

**Files:**
- Create: `src/btwin/core/common_record_models.py`
- Test: `tests/test_core/test_common_record_models.py`
- Reference: `src/btwin/core/collab_models.py`
- Reference: `src/btwin/core/indexer_models.py`

**Step 1: Write the failing test**
Cover shared metadata contract fields:
- `doc_version`
- `status`
- `created_at`
- `updated_at`
- `record_type`

Run: `uv run pytest -q tests/test_core/test_common_record_models.py`
Expected: FAIL because file does not exist.

**Step 2: Write minimal implementation**
Add reusable base model(s) for document metadata shared by workflow/dashboard records.

**Step 3: Run test to verify it passes**
Run: `uv run pytest -q tests/test_core/test_common_record_models.py`
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/core/common_record_models.py tests/test_core/test_common_record_models.py
git commit -m "feat(core): add shared record metadata models"
```

---

### Task 2: Workflow-compatible storage paths and indexability

**Files:**
- Modify: `src/btwin/core/storage.py`
- Modify: `src/btwin/core/indexer.py` (only if required)
- Test: `tests/test_core/test_common_foundation_storage.py`
- Docs: `docs/reports/2026-03-06-common-foundation-indexer-check.md`

**Step 1: Write the failing test**
Cover:
- shared/workflow docs saved with deterministic paths
- docs appear in `list_indexable_documents()`
- `record_type` is stable/filterable

Run: `uv run pytest -q tests/test_core/test_common_foundation_storage.py`
Expected: FAIL

**Step 2: Write minimal implementation**
Extend storage/indexable document enumeration to include foundation/workflow namespace docs.

**Step 3: Run test to verify it passes**
Run: `uv run pytest -q tests/test_core/test_common_foundation_storage.py`
Expected: PASS

**Step 4: Write compatibility check doc**
Document what was reused vs what changed.

**Step 5: Commit**
```bash
git add src/btwin/core/storage.py src/btwin/core/indexer.py tests/test_core/test_common_foundation_storage.py docs/reports/2026-03-06-common-foundation-indexer-check.md
git commit -m "feat(storage): make common foundation docs indexable"
```

---

### Task 3: Shared API structure scaffold

**Files:**
- Modify: `src/btwin/api/collab_api.py`
- Create: `tests/test_api/test_common_foundation_api.py`

**Step 1: Write the failing test**
Cover existence of foundational route grouping and placeholders:
- `/api/workflows/health` (or equivalent base route)
- `/api/entries/health`
- `/api/sources/health`

Run: `uv run pytest -q tests/test_api/test_common_foundation_api.py`
Expected: FAIL

**Step 2: Write minimal implementation**
Add thin scaffold endpoints or route grouping that future features can extend cleanly.
Do not build full feature endpoints yet.

**Step 3: Run test to verify it passes**
Run: `uv run pytest -q tests/test_api/test_common_foundation_api.py`
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/api/collab_api.py tests/test_api/test_common_foundation_api.py
git commit -m "feat(api): add common foundation route scaffold"
```

---

### Task 4: Shared UI shell

**Files:**
- Modify: `src/btwin/api/collab_api.py`
- Create: `tests/test_api/test_common_foundation_ui.py`

**Step 1: Write the failing test**
Cover:
- `/app` or `/ui` shell page loads
- navigation links for workflows / entries / sources / summary / ops exist

Run: `uv run pytest -q tests/test_api/test_common_foundation_ui.py`
Expected: FAIL

**Step 2: Write minimal implementation**
Add simple HTML navigation shell only.
No feature pages required yet.

**Step 3: Run test to verify it passes**
Run: `uv run pytest -q tests/test_api/test_common_foundation_ui.py`
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/api/collab_api.py tests/test_api/test_common_foundation_ui.py
git commit -m "feat(ui): add shared shell for workflow and dashboard"
```

---

### Task 5: Shared audit/recovery contract doc + tests

**Files:**
- Create: `docs/reports/2026-03-06-common-foundation-recovery-contract.md`
- Create: `tests/test_core/test_common_foundation_recovery.py`
- Modify: `src/btwin/core/audit.py` only if required

**Step 1: Write the failing test**
Cover minimal recovery assumptions:
- persisted state sufficient to compute resume pointer
- audit rows retain identifiers needed for reconstruction

Run: `uv run pytest -q tests/test_core/test_common_foundation_recovery.py`
Expected: FAIL

**Step 2: Write minimal implementation**
Add only what is necessary so the contract is testable.
If code change is not needed, implement the test against current behavior and add the contract doc.

**Step 3: Run test to verify it passes**
Run: `uv run pytest -q tests/test_core/test_common_foundation_recovery.py`
Expected: PASS

**Step 4: Commit**
```bash
git add docs/reports/2026-03-06-common-foundation-recovery-contract.md tests/test_core/test_common_foundation_recovery.py src/btwin/core/audit.py
git commit -m "docs(core): define common foundation recovery contract"
```

---

### Task 6: Full verification and handoff doc

**Files:**
- Create: `docs/reports/2026-03-06-common-foundation-test-guide.md`
- Modify: `README.md` (if necessary)

**Step 1: Write handoff/test guide**
Include:
- what common foundation now provides
- what it does not yet provide
- how to verify the foundation manually
- what workflow/dashboard work can now build on top

**Step 2: Run full suite**
Run: `uv run pytest -q`
Expected: PASS

**Step 3: Commit**
```bash
git add docs/reports/2026-03-06-common-foundation-test-guide.md README.md
git commit -m "docs(test): add common foundation verification guide"
```
