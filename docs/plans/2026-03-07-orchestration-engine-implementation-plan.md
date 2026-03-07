# Orchestration Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the B-TWIN orchestration engine that keeps multi-step workflows moving through persisted handoffs, deterministic state transitions, continuation context rebuilding, and recovery-safe redispatch.

**Architecture:** Build on the existing workflow MVP direction, but tighten the runtime into five layers: ingress, workflow engine, persistence, execution adapter, and watchdog. Use event records as source of truth, materialized state as cache, and idempotent transition dispatch so workflows continue without requiring a fresh user message after every step.

**Tech Stack:** Python, FastAPI, Typer, Pydantic, markdown/frontmatter storage, existing B-TWIN indexer stack, pytest

---

### Task 1: Consolidate design rules into implementation-facing references

**Files:**
- Modify: `docs/plans/2026-03-07-orchestration-engine-design.md`
- Reference: `docs/reports/2026-03-07-orchestration-design-feedback-response.md`
- Reference: `docs/reports/2026-03-07-orchestration-design-followup-response.md`

**Step 1: Update the design doc header and scope text**
Add/confirm:
- 5-layer architecture
- source-of-truth rules
- phase/status separation
- trigger priority
- MVP sequential-scope statement

**Step 2: Add review normalization and lifecycle rules**
Document:
- `CanonicalReviewResult`
- `ReviewFinding`
- TaskRun open → closed → immutable lifecycle
- `awaiting_input` / `blocked` / `interrupted` / `escalated` boundaries

**Step 3: Add transition examples section**
Include at least:
- implement success → review queued
- review fail → fix queued
- duplicate completion → skipped
- watchdog recovery
- escalation after retry threshold

**Step 4: Sanity-read the design doc for contradiction removal**
Check for conflicts between:
- append-only event language
- mutable TaskRun lifecycle language
- handoff-driven coordination vs completion-event-driven transitions

**Step 5: Commit**
```bash
git add docs/plans/2026-03-07-orchestration-engine-design.md
git commit -m "docs(design): consolidate orchestration engine runtime rules"
```

---

### Task 2: Workflow core models — phase, status, runs, reviews, handoffs

**Files:**
- Create: `src/btwin/core/workflow_models.py`
- Test: `tests/test_core/test_workflow_models.py`
- Reference: `src/btwin/core/common_record_models.py`

**Step 1: Write failing model tests**
Cover:
- `Phase`, `RunStatus`, `TaskStatus`, `WorkflowStatus`
- `EpicRecord`, `TaskRecord`, `TaskRunRecord`, `ReviewRecord`, `HandoffRecord`
- `TaskRunRecord` lifecycle constraints
- `CanonicalReviewResult` normalization input/output model validity

Run:
```bash
uv run pytest -q tests/test_core/test_workflow_models.py
```
Expected: FAIL because the models do not exist or are incomplete.

**Step 2: Implement minimal models**
Add typed models for:
- workflow/task/run/review/handoff records
- review findings/result models
- basic validation for status/phase values and required identifiers

**Step 3: Add TaskRun lifecycle helpers**
Implement helpers or methods that make it hard to:
- mutate closed runs
- write illegal status transitions

**Step 4: Re-run model tests**
Run:
```bash
uv run pytest -q tests/test_core/test_workflow_models.py
```
Expected: PASS

**Step 5: Commit**
```bash
git add src/btwin/core/workflow_models.py tests/test_core/test_workflow_models.py
git commit -m "feat(workflow): add orchestration engine record models"
```

---

### Task 3: Persist workflow, run, review, and handoff documents

**Files:**
- Modify: `src/btwin/core/storage.py`
- Test: `tests/test_core/test_workflow_storage.py`
- Test: `tests/test_core/test_workflow_handoffs.py`

**Step 1: Write failing storage tests for workflow records**
Cover:
- deterministic path layout for workflow/task/run/handoff docs
- save/read/list for epics, tasks, runs, reviews, handoffs
- frontmatter includes core metadata and identifiers
- project-scoped workflow path behavior

Run:
```bash
uv run pytest -q tests/test_core/test_workflow_storage.py tests/test_core/test_workflow_handoffs.py
```
Expected: FAIL because storage helpers do not exist or are incomplete.

**Step 2: Implement storage helpers**
Add methods such as:
- `save_workflow_epic(...)`
- `save_workflow_task(...)`
- `save_task_run(...)`
- `save_review_record(...)`
- `save_handoff_record(...)`
- `list_task_runs(task_id)`
- `list_handoffs(task_id)`

**Step 3: Enforce storage invariants**
Make sure:
- closed TaskRun records are rewritten only through valid close/update path
- review/handoff records are append-only once written
- materialized task/workflow status fields remain writable summaries

**Step 4: Re-run storage tests**
Run:
```bash
uv run pytest -q tests/test_core/test_workflow_storage.py tests/test_core/test_workflow_handoffs.py
```
Expected: PASS

**Step 5: Commit**
```bash
git add src/btwin/core/storage.py tests/test_core/test_workflow_storage.py tests/test_core/test_workflow_handoffs.py
git commit -m "feat(storage): persist workflow runs reviews and handoffs"
```

---

### Task 4: Source-of-truth and recomputation helpers

**Files:**
- Create: `src/btwin/core/workflow_engine.py`
- Test: `tests/test_core/test_workflow_engine_state.py`
- Reference: `src/btwin/core/workflow_models.py`

**Step 1: Write failing state-rebuild tests**
Cover:
- recomputing task state from latest run + review records
- recomputing workflow current step from ordered tasks
- correcting materialized state when it disagrees with event records

Run:
```bash
uv run pytest -q tests/test_core/test_workflow_engine_state.py
```
Expected: FAIL because the workflow engine helpers do not exist.

**Step 2: Implement state-rebuild helpers**
Add functions like:
- `rebuild_task_state(...)`
- `rebuild_workflow_state(...)`
- `detect_state_inconsistency(...)`

**Step 3: Re-run tests**
Run:
```bash
uv run pytest -q tests/test_core/test_workflow_engine_state.py
```
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/core/workflow_engine.py tests/test_core/test_workflow_engine_state.py
git commit -m "feat(workflow): add source-of-truth rebuild helpers"
```

---

### Task 5: Transition gate and next-step computation

**Files:**
- Modify: `src/btwin/core/workflow_gate.py`
- Modify: `src/btwin/core/workflow_engine.py`
- Test: `tests/test_core/test_workflow_gate.py`
- Test: `tests/test_core/test_workflow_transitions.py`

**Step 1: Write failing transition tests**
Cover:
- implement complete → review queued
- review fail → fix queued
- fix complete → review queued
- review pass → task done
- previous task done → next task unlocked
- hold verdict → awaiting_input
- retry threshold exceeded → escalated

Run:
```bash
uv run pytest -q tests/test_core/test_workflow_gate.py tests/test_core/test_workflow_transitions.py
```
Expected: FAIL because transition rules are incomplete.

**Step 2: Implement transition gate logic**
Add pure transition logic returning a structured next-step decision.

**Step 3: Encode trigger-agnostic next-step computation**
Make sure completion, resume, and watchdog all use the same transition computation path.

**Step 4: Re-run tests**
Run:
```bash
uv run pytest -q tests/test_core/test_workflow_gate.py tests/test_core/test_workflow_transitions.py
```
Expected: PASS

**Step 5: Commit**
```bash
git add src/btwin/core/workflow_gate.py src/btwin/core/workflow_engine.py tests/test_core/test_workflow_gate.py tests/test_core/test_workflow_transitions.py
git commit -m "feat(workflow): add deterministic transition engine"
```

---

### Task 6: Review normalization layer

**Files:**
- Modify: `src/btwin/core/workflow_engine.py`
- Test: `tests/test_core/test_review_normalization.py`

**Step 1: Write failing normalization tests**
Cover the normalization table:
- structured verdict + findings
- verdict only
- findings only
- no structured output
- conflicting pass + critical finding

Run:
```bash
uv run pytest -q tests/test_core/test_review_normalization.py
```
Expected: FAIL because the canonical normalization function does not exist.

**Step 2: Implement review normalization**
Add a function such as:
- `normalize_review_result(raw_output, review_round)`

It should always return a canonical result.

**Step 3: Re-run tests**
Run:
```bash
uv run pytest -q tests/test_core/test_review_normalization.py
```
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/core/workflow_engine.py tests/test_core/test_review_normalization.py
git commit -m "feat(workflow): add canonical review normalization"
```

---

### Task 7: Idempotent dispatch and transition keys

**Files:**
- Create: `src/btwin/core/workflow_dispatcher.py`
- Test: `tests/test_core/test_workflow_dispatcher.py`
- Test: `tests/test_core/test_workflow_idempotency.py`

**Step 1: Write failing dispatcher tests**
Cover:
- dispatch next step once on completion
- duplicate completion event does not create duplicate run
- watchdog recovery skips already-dispatched transition
- manual retry creates distinct transition key

Run:
```bash
uv run pytest -q tests/test_core/test_workflow_dispatcher.py tests/test_core/test_workflow_idempotency.py
```
Expected: FAIL because dispatcher/idempotency logic does not exist.

**Step 2: Implement transition-key recording and dispatch guard**
Add:
- transition key generation
- persisted transition ledger or equivalent durable guard
- `try_dispatch_next(...)`

**Step 3: Re-run tests**
Run:
```bash
uv run pytest -q tests/test_core/test_workflow_dispatcher.py tests/test_core/test_workflow_idempotency.py
```
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/core/workflow_dispatcher.py tests/test_core/test_workflow_dispatcher.py tests/test_core/test_workflow_idempotency.py
git commit -m "feat(workflow): add idempotent next-step dispatcher"
```

---

### Task 8: Completion handler built on runtime-observable facts

**Files:**
- Modify: `src/btwin/api/collab_api.py`
- Modify: `src/btwin/core/workflow_dispatcher.py`
- Test: `tests/test_api/test_workflow_completion_api.py`

**Step 1: Write failing completion API tests**
Cover:
- completion with structured handoff
- completion without structured output but with diff/log refs
- completion with empty output leading to `awaiting_input`
- review completion producing canonical review record

Run:
```bash
uv run pytest -q tests/test_api/test_workflow_completion_api.py
```
Expected: FAIL because the completion route/handler is incomplete.

**Step 2: Implement completion handler flow**
Ensure it:
- persists run completion facts
- writes handoff/review records as applicable
- computes next transition
- persists materialized state updates
- dispatches next run if needed

**Step 3: Re-run tests**
Run:
```bash
uv run pytest -q tests/test_api/test_workflow_completion_api.py
```
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/api/collab_api.py src/btwin/core/workflow_dispatcher.py tests/test_api/test_workflow_completion_api.py
git commit -m "feat(api): add workflow completion and handoff handling"
```

---

### Task 9: Continuation context builder and prompt bundles

**Files:**
- Create: `src/btwin/core/workflow_context.py`
- Test: `tests/test_core/test_workflow_context.py`
- Reference: existing retrieval/indexer utilities

**Step 1: Write failing context-builder tests**
Cover:
- implementer bundle creation
- reviewer bundle creation
- fix bundle creation
- deterministic output from same persisted inputs
- optional historical workflow enrichment

Run:
```bash
uv run pytest -q tests/test_core/test_workflow_context.py
```
Expected: FAIL because the context builder does not exist.

**Step 2: Implement context builder**
Add:
- typed input/output models
- phase-aware bundle assembly
- stop/escalation conditions
- optional similar-past-task enrichment with graceful fallback when no history exists

**Step 3: Re-run tests**
Run:
```bash
uv run pytest -q tests/test_core/test_workflow_context.py
```
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/core/workflow_context.py tests/test_core/test_workflow_context.py
git commit -m "feat(workflow): add continuation context builder"
```

---

### Task 10: Recovery APIs and watchdog

**Files:**
- Create: `src/btwin/core/workflow_watchdog.py`
- Modify: `src/btwin/api/collab_api.py`
- Test: `tests/test_core/test_workflow_watchdog.py`
- Test: `tests/test_api/test_workflow_recovery_api.py`

**Step 1: Write failing recovery tests**
Cover:
- stale run detection
- orphaned completed run with no follow-up detection
- watchdog recovery requeues same phase
- resume API ignores already-running run
- watchdog does not preempt active healthy run

Run:
```bash
uv run pytest -q tests/test_core/test_workflow_watchdog.py tests/test_api/test_workflow_recovery_api.py
```
Expected: FAIL because watchdog/recovery is incomplete.

**Step 2: Implement watchdog + resume behavior**
Add:
- stale run scan
- orphaned transition scan
- recovery dispatch path using same idempotent dispatcher
- resume endpoint using same logic

**Step 3: Re-run tests**
Run:
```bash
uv run pytest -q tests/test_core/test_workflow_watchdog.py tests/test_api/test_workflow_recovery_api.py
```
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/core/workflow_watchdog.py src/btwin/api/collab_api.py tests/test_core/test_workflow_watchdog.py tests/test_api/test_workflow_recovery_api.py
git commit -m "feat(workflow): add recovery watchdog and resume hooks"
```

---

### Task 11: MCP/headless workflow tool surface

**Files:**
- Modify: `src/btwin/mcp/proxy.py`
- Modify: `src/btwin/core/btwin.py`
- Test: `tests/test_mcp/test_workflow_tools.py`

**Step 1: Write failing MCP tool tests**
Cover:
- workflow creation tool
- workflow status tool
- complete phase tool
- workflow search tool

Run:
```bash
uv run pytest -q tests/test_mcp/test_workflow_tools.py
```
Expected: FAIL because the MCP-facing workflow tools do not exist.

**Step 2: Implement minimal tool surface**
Expose tools like:
- `btwin_create_workflow`
- `btwin_workflow_status`
- `btwin_complete_phase`
- `btwin_search_workflows`

**Step 3: Re-run tests**
Run:
```bash
uv run pytest -q tests/test_mcp/test_workflow_tools.py
```
Expected: PASS

**Step 4: Commit**
```bash
git add src/btwin/mcp/proxy.py src/btwin/core/btwin.py tests/test_mcp/test_workflow_tools.py
git commit -m "feat(mcp): add orchestration workflow tools"
```

---

### Task 12: Docs, verification, and handoff

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Create: `docs/reports/2026-03-07-orchestration-engine-test-guide.md`

**Step 1: Update usage docs**
Document:
- workflow lifecycle
- handoff model
- completion/resume/watchdog behavior
- terminal states vs checkpoints
- MVP sequential-scope constraint

**Step 2: Add verification guide**
Include manual checks for:
- implement → review progression
- review fail → fix → review
- duplicate completion tolerance
- watchdog stale-run recovery
- escalation path

**Step 3: Run targeted verification**
Run:
```bash
uv run pytest -q tests/test_core/test_workflow_models.py \
  tests/test_core/test_workflow_storage.py \
  tests/test_core/test_workflow_engine_state.py \
  tests/test_core/test_workflow_gate.py \
  tests/test_core/test_review_normalization.py \
  tests/test_core/test_workflow_dispatcher.py \
  tests/test_core/test_workflow_context.py \
  tests/test_core/test_workflow_watchdog.py \
  tests/test_api/test_workflow_completion_api.py \
  tests/test_api/test_workflow_recovery_api.py \
  tests/test_mcp/test_workflow_tools.py
```
Expected: PASS

**Step 4: Run full suite**
Run:
```bash
uv run pytest -q
```
Expected: PASS

**Step 5: Commit**
```bash
git add README.md docs/runbook.md docs/reports/2026-03-07-orchestration-engine-test-guide.md
git commit -m "docs(workflow): add orchestration engine usage and verification guide"
```

---

Plan complete and saved to `docs/plans/2026-03-07-orchestration-engine-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
