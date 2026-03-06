# Workflow Orchestration MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a B-TWIN MVP that can manage epics and child tasks with persisted workflow state, automatic implement→review→fix loops per task, and sequential auto-progression across tasks.

**Architecture:** Reuse B-TWIN’s existing markdown + frontmatter storage, indexer, checksum/doc_version, and audit patterns. Add a workflow layer that stores epics/tasks/task runs as documents, enforces transitions in code, and exposes a minimal API/UI for queueing, progression, retry escalation, and recovery.

**Tech Stack:** Python, FastAPI, Typer, Pydantic, markdown/frontmatter storage, existing B-TWIN indexer/vector stack, pytest

---

### Task 1: Workflow domain models and storage shape

**Files:**
- Create: `src/btwin/core/workflow_models.py`
- Modify: `src/btwin/core/storage.py`
- Test: `tests/test_core/test_workflow_models.py`
- Test: `tests/test_core/test_workflow_storage.py`
- Reference: `src/btwin/core/collab_models.py`
- Reference: `src/btwin/core/storage.py`

**Step 1: Write failing model tests**

Cover:
- `EpicRecord`
- `TaskRecord`
- `TaskRunRecord`
- required identifiers (`workflowId`, `epicId`, `taskId`, `runId`)
- enum fields for `status`, `phase`, `verdict`
- retry counter default and validation

Run: `uv run pytest -q tests/test_core/test_workflow_models.py`
Expected: FAIL because file/models do not exist.

**Step 2: Implement minimal workflow models**

Add Pydantic/dataclass models with at least:
- Epic: title, goal, scope, done_criteria, priority, status, created_at
- Task: epic_id, order, title, spec, status, assignee_agent, depends_on
- TaskRun: task_id, phase (`implement|review|fix`), status, retry_count, last_verdict, blocker_reason

**Step 3: Run model tests**

Run: `uv run pytest -q tests/test_core/test_workflow_models.py`
Expected: PASS

**Step 4: Write failing storage tests**

Cover:
- save/read/list epics
- save/read/list tasks for an epic
- save/read/list task runs
- storage path layout under workflow namespace
- frontmatter includes `doc_version`

Run: `uv run pytest -q tests/test_core/test_workflow_storage.py`
Expected: FAIL because storage methods do not exist.

**Step 5: Implement workflow storage methods**

Add storage methods such as:
- `save_workflow_epic(...)`
- `save_workflow_task(...)`
- `save_workflow_task_run(...)`
- `list_workflow_epics()`
- `list_workflow_tasks(epic_id)`
- `list_workflow_task_runs(task_id)`

Use markdown + frontmatter and keep paths deterministic.

**Step 6: Run storage tests**

Run: `uv run pytest -q tests/test_core/test_workflow_storage.py`
Expected: PASS

**Step 7: Commit**

```bash
git add src/btwin/core/workflow_models.py src/btwin/core/storage.py tests/test_core/test_workflow_models.py tests/test_core/test_workflow_storage.py
git commit -m "feat(workflow): add epic task and run storage models"
```

---

### Task 2: Workflow transition engine and retry/escalation rules

**Files:**
- Create: `src/btwin/core/workflow_gate.py`
- Test: `tests/test_core/test_workflow_gate.py`
- Reference: `src/btwin/core/gate.py`

**Step 1: Write failing transition tests**

Cover:
- implement complete → review queued
- review fail → fix required
- fix complete → review queued
- review pass → task done
- task done unlocks next task
- retry threshold exceeded → `human_review_required`

Run: `uv run pytest -q tests/test_core/test_workflow_gate.py`
Expected: FAIL because module does not exist.

**Step 2: Implement minimal gate**

Add pure transition functions with deterministic outputs.
Include configurable `max_review_failures`.
Do not depend on FastAPI.

**Step 3: Run gate tests**

Run: `uv run pytest -q tests/test_core/test_workflow_gate.py`
Expected: PASS

**Step 4: Commit**

```bash
git add src/btwin/core/workflow_gate.py tests/test_core/test_workflow_gate.py
git commit -m "feat(workflow): add task transition and escalation gate"
```

---

### Task 3: Indexer compatibility check for workflow docs

**Files:**
- Modify: `src/btwin/core/storage.py`
- Modify: `src/btwin/core/indexer.py` (only if needed)
- Test: `tests/test_core/test_workflow_indexing.py`
- Docs: `docs/reports/2026-03-06-workflow-indexer-compat.md`

**Step 1: Write failing indexing tests**

Cover:
- workflow docs appear in `list_indexable_documents()`
- `record_type` for workflow docs is stable and filterable
- checksum/doc_version update on task doc change

Run: `uv run pytest -q tests/test_core/test_workflow_indexing.py`
Expected: FAIL because workflow docs are not listed yet.

**Step 2: Implement minimal indexing support**

Add workflow namespace paths to storage iteration.
Ensure workflow docs are represented in index metadata with fields needed for retrieval.

**Step 3: Run indexing tests**

Run: `uv run pytest -q tests/test_core/test_workflow_indexing.py`
Expected: PASS

**Step 4: Write compatibility report**

Create `docs/reports/2026-03-06-workflow-indexer-compat.md` including:
- what worked unchanged
- what required code changes
- what remains future work

**Step 5: Commit**

```bash
git add src/btwin/core/storage.py src/btwin/core/indexer.py tests/test_core/test_workflow_indexing.py docs/reports/2026-03-06-workflow-indexer-compat.md
git commit -m "feat(workflow): make workflow docs indexable"
```

---

### Task 4: Workflow API scaffold

**Files:**
- Modify: `src/btwin/api/collab_api.py`
- Test: `tests/test_api/test_workflow_api.py`
- Reference: existing collab/indexer API patterns

**Step 1: Write failing API tests**

Cover endpoints:
- `POST /api/workflows/epics`
- `GET /api/workflows/epics`
- `POST /api/workflows/tasks`
- `GET /api/workflows/tasks`
- `POST /api/workflows/task-runs`
- `POST /api/workflows/task-runs/{run_id}/complete`
- `POST /api/workflows/task-runs/{run_id}/review`

Run: `uv run pytest -q tests/test_api/test_workflow_api.py`
Expected: FAIL because endpoints do not exist.

**Step 2: Implement minimal API endpoints**

Reuse request/response/error style from collab API.
Persist through new workflow storage methods.
Route review results through workflow gate logic.

**Step 3: Run API tests**

Run: `uv run pytest -q tests/test_api/test_workflow_api.py`
Expected: PASS

**Step 4: Commit**

```bash
git add src/btwin/api/collab_api.py tests/test_api/test_workflow_api.py
git commit -m "feat(workflow): add epic task and run api scaffold"
```

---

### Task 5: Minimal queue/progression dashboard UI

**Files:**
- Modify: `src/btwin/api/collab_api.py`
- Test: `tests/test_api/test_workflow_ui.py`

**Step 1: Write failing UI tests**

Cover:
- `/workflows` page loads
- page contains epic/task/run sections
- page exposes next action and blocked status text

Run: `uv run pytest -q tests/test_api/test_workflow_ui.py`
Expected: FAIL because UI does not exist.

**Step 2: Implement minimal HTML UI**

Show:
- epic list
- ordered tasks under an epic
- current phase/status/verdict
- next actionable task
- human-review-required badge when escalated

No advanced styling needed.

**Step 3: Run UI tests**

Run: `uv run pytest -q tests/test_api/test_workflow_ui.py`
Expected: PASS

**Step 4: Commit**

```bash
git add src/btwin/api/collab_api.py tests/test_api/test_workflow_ui.py
git commit -m "feat(workflow): add minimal orchestration dashboard ui"
```

---

### Task 6: Auto-progression + recovery hooks

**Files:**
- Create: `src/btwin/core/workflow_dispatcher.py`
- Modify: `src/btwin/api/collab_api.py`
- Modify: `scripts/end_of_batch_sync.sh` (only if useful for recovery docs)
- Test: `tests/test_core/test_workflow_dispatcher.py`
- Test: `tests/test_api/test_workflow_recovery_api.py`

**Step 1: Write failing dispatcher tests**

Cover:
- after PASS review, next task becomes actionable automatically
- after FAIL review under threshold, fix task/run is queued automatically
- over threshold, task becomes `human_review_required`
- interrupted in-progress task can be recovered from saved state

Run: `uv run pytest -q tests/test_core/test_workflow_dispatcher.py tests/test_api/test_workflow_recovery_api.py`
Expected: FAIL because dispatcher does not exist.

**Step 2: Implement dispatcher**

Implement functions that:
- compute next action from persisted state
- create new task runs automatically
- support recovery from last run state

Keep it synchronous/in-process for MVP.
Do not build a full async queue worker yet.

**Step 3: Run dispatcher/recovery tests**

Run: `uv run pytest -q tests/test_core/test_workflow_dispatcher.py tests/test_api/test_workflow_recovery_api.py`
Expected: PASS

**Step 4: Commit**

```bash
git add src/btwin/core/workflow_dispatcher.py src/btwin/api/collab_api.py tests/test_core/test_workflow_dispatcher.py tests/test_api/test_workflow_recovery_api.py
git commit -m "feat(workflow): add auto progression and recovery dispatcher"
```

---

### Task 7: MVP docs and full verification

**Files:**
- Create: `docs/reports/2026-03-06-workflow-orchestration-mvp-test-guide.md`
- Modify: `README.md`
- Modify: `docs/runbook.md`

**Step 1: Update docs**

Document:
- workflow concepts (epic/task/run)
- retry escalation rule (N failures)
- how to create a workflow
- how to inspect blocked tasks
- how to recover an interrupted task
- indexer compatibility caveat

**Step 2: Run full suite**

Run: `uv run pytest -q`
Expected: PASS

**Step 3: Commit**

```bash
git add README.md docs/runbook.md docs/reports/2026-03-06-workflow-orchestration-mvp-test-guide.md
git commit -m "docs(workflow): add orchestration mvp usage and recovery guide"
```

---

Plan complete and saved to `docs/plans/2026-03-06-workflow-orchestration-mvp.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
