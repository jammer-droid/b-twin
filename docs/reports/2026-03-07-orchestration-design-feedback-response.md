---
doc_version: 1
last_updated: 2026-03-07
status: draft
responds_to:
  - docs/reports/2026-03-07-agent-orchestration-framework-report-feedback.md
updates:
  - docs/plans/2026-03-07-orchestration-engine-design.md
---

# Orchestration Design — Feedback Response and Design Corrections

## Purpose

This document responds to the feedback on the agent orchestration framework reference report.
It addresses each identified gap and provides the corrected design decisions that should be incorporated into the orchestration engine design.

The feedback identified 7 gaps. All 7 are valid and accepted. This document provides the corrected design for each.

---

## Gap 1: Architectural Layer Separation

### Feedback summary
The design blurs too many concerns into "the MCP server/runtime." Implementation will create a monolithic module without explicit layer separation.

### Accepted. Corrected design:

```
┌─────────────────────────────────────────────────┐
│  Layer 1: MCP / API Ingress                     │
│  - receives MCP tool calls and HTTP requests    │
│  - validates input, routes to workflow engine    │
│  - returns responses to clients                 │
│  - owns: server.py, proxy.py, collab_api.py     │
├─────────────────────────────────────────────────┤
│  Layer 2: Workflow Engine                       │
│  - owns workflow state transitions              │
│  - computes next step from current state        │
│  - enforces phase/status rules                  │
│  - stateless: reads state, computes, writes     │
│  - owns: workflow_gate.py, workflow_engine.py    │
├─────────────────────────────────────────────────┤
│  Layer 3: Persistence                           │
│  - stores workflow/task/run/handoff/audit docs   │
│  - markdown + YAML frontmatter (existing)       │
│  - indexer integration for searchability        │
│  - owns: storage.py, indexer.py, audit.py        │
├─────────────────────────────────────────────────┤
│  Layer 4: Execution Adapter                     │
│  - invokes provider-specific workers            │
│  - builds continuation context bundles          │
│  - manages execution sessions                   │
│  - owns: workflow_dispatcher.py, context.py      │
├─────────────────────────────────────────────────┤
│  Layer 5: Watchdog / Sweep                      │
│  - periodic scan of workflow state              │
│  - detects stale runs, orphaned transitions     │
│  - idempotent redispatch (recovery only)        │
│  - owns: workflow_watchdog.py                    │
└─────────────────────────────────────────────────┘
```

### Ownership rules

- Layer 1 **never** computes workflow transitions — it delegates to Layer 2
- Layer 2 **never** writes to storage directly — it returns transition results that Layer 1 or Layer 4 persist via Layer 3
- Layer 3 is the **only** writer of durable state
- Layer 4 **never** decides what the next step is — it receives dispatch instructions from Layer 2
- Layer 5 **only** triggers recovery actions — it is never the primary progression path

### File mapping

| File | Layer | Responsibility |
|------|-------|---------------|
| `mcp/server.py` | 1 | MCP tool handlers |
| `api/collab_api.py` | 1 | HTTP API routes |
| `core/workflow_engine.py` | 2 | State transition computation |
| `core/workflow_gate.py` | 2 | Transition rules and guards |
| `core/storage.py` | 3 | Document persistence |
| `core/indexer.py` | 3 | Search indexing |
| `core/audit.py` | 3 | Audit trail |
| `core/workflow_dispatcher.py` | 4 | Execution dispatch |
| `core/workflow_context.py` | 4 | Continuation context builder |
| `core/workflow_watchdog.py` | 5 | Stale/orphan detection and recovery |

---

## Gap 2: Source of Truth Definition

### Feedback summary
The design does not distinguish event records (facts) from materialized state (summaries) from recomputable views. Recovery logic will be inconsistent without this.

### Accepted. Corrected design:

#### Record categories

| Category | Examples | Mutability | Recovery role |
|----------|----------|-----------|---------------|
| **Event records** (facts) | TaskRunRecord, HandoffRecord, ReviewRecord, AuditEntry | Append-only, immutable once written | Primary source of truth for recovery |
| **Materialized state** (summaries) | `task.status`, `workflow.status`, `workflow.current_step` | Mutable, updated on each transition | Trusted first for normal operation |
| **Derived views** (recomputable) | "next actionable task", "blocked tasks", dashboard aggregations | Not stored, computed on read | Always recomputed from event records + materialized state |

#### Source of truth rules

1. **`task.status` is materialized, not authoritative.**
   - Normal path: read `task.status` directly
   - Recovery path: recompute from latest `TaskRunRecord` + `ReviewRecord` for that task
   - If materialized state and recomputed state disagree: **recomputed wins**, materialized is corrected

2. **`workflow.current_step` is materialized, not authoritative.**
   - Derived from: ordered task list + each task's status
   - Recovery: scan all tasks, find first non-terminal task → that is current_step

3. **Event records are append-only and immutable.**
   - TaskRunRecord: created when run starts, status updated on completion, never deleted
   - HandoffRecord: written once on phase completion, never modified
   - ReviewRecord: written once per review verdict, never modified
   - AuditEntry: append-only JSONL, never modified

4. **Recovery behavior:**
   - Step 1: trust materialized state
   - Step 2: if inconsistency detected (watchdog or manual), recompute from event records
   - Step 3: correct materialized state to match recomputed state
   - Step 4: log the correction as an audit entry

#### Invariant

> Materialized state is a performance cache. Event records are the source of truth. Any materialized state can be rebuilt from event records.

---

## Gap 3: Completion Handler — Runtime-Observable Facts

### Feedback summary
The completion handler assumes structured output from the model. In practice, provider outputs may be inconsistent. The handler should be designed around what the runtime can reliably observe.

### Accepted. Corrected design:

#### Minimum completion input (runtime-observable)

```python
class RunCompletionEvent(BaseModel):
    """What the runtime can always observe, regardless of provider."""

    task_id: str
    run_id: str
    phase: Phase
    exit_code: int              # 0 = success, non-zero = error
    started_at: datetime
    completed_at: datetime
    log_ref: str | None = None  # path to stdout/stderr capture
    diff_ref: str | None = None # path to git diff or artifact
```

#### Optional structured output (model-provided, not guaranteed)

```python
class StructuredRunOutput(BaseModel):
    """What the model may provide if it follows the handoff protocol."""

    summary: str | None = None
    changed_files: list[str] | None = None
    decisions: list[str] | None = None
    open_issues: list[str] | None = None
    review_request: ReviewRequest | None = None
    fix_request: FixRequest | None = None
    completion_report: CompletionReport | None = None
```

#### Completion handler behavior

```
on_run_completed(event: RunCompletionEvent, output: StructuredRunOutput | None):

    1. persist RunCompletionEvent as event record (always)
    2. if output is provided:
         persist HandoffRecord from structured output
    3. if output is missing:
         create minimal HandoffRecord with:
           summary = "run completed without structured output"
           changed_files = extract from diff_ref if available
    4. compute next transition via workflow engine (Layer 2)
    5. persist materialized state updates
    6. if next step exists:
         dispatch via execution adapter (Layer 4)
    7. log audit entry
```

#### Design invariant

> The completion handler must function correctly even when the model provides no structured output. Structured handoff data improves context quality but is never required for workflow progression.

---

## Gap 4: Idempotency Model

### Feedback summary
Multiple triggers (completion event, resume, watchdog, manual retry) can advance the workflow. Without idempotent transitions, duplicate dispatch is a major risk.

### Accepted. Corrected design:

#### Transition key

Each workflow transition is identified by a unique transition key:

```python
transition_key = f"{task_id}:{run_id}:{from_phase}:{from_status}→{to_phase}:{to_status}"
```

#### Dispatch-at-most-once semantics

```python
def try_dispatch_next(task_id: str, run_id: str) -> DispatchResult:
    """Attempt to dispatch the next step. Idempotent."""

    # 1. read current materialized state
    task = storage.read_task(task_id)
    latest_run = storage.read_run(run_id)

    # 2. check if transition already dispatched
    transition_key = compute_transition_key(task, latest_run)
    if storage.transition_exists(transition_key):
        return DispatchResult(status="already_dispatched", skipped=True)

    # 3. compute next step
    next_step = workflow_engine.compute_next(task, latest_run)
    if next_step is None:
        return DispatchResult(status="no_next_step")

    # 4. atomically: create next run + record transition key
    new_run = storage.create_run(next_step)
    storage.record_transition(transition_key, new_run.run_id)

    # 5. dispatch
    dispatcher.dispatch(new_run)
    return DispatchResult(status="dispatched", run_id=new_run.run_id)
```

#### Duplicate tolerance rules

| Trigger | Behavior if transition already dispatched |
|---------|------------------------------------------|
| Completion event (duplicate) | Skip, log "already dispatched" |
| Resume request | Skip if already running, re-dispatch if queued but not started |
| Watchdog recovery | Skip if transition exists, re-dispatch only if orphaned |
| Manual admin retry | Always allowed — creates new transition key with `retry` suffix |

#### Design invariant

> Workflow next-step computation may run multiple times, but each transition must be dispatched at most once. The transition key is the deduplication mechanism.

---

## Gap 5: Phase vs Status Separation

### Feedback summary
Phase (what kind of work) and status (operational state) are conflated. A task can be in the same phase but different operational states.

### Accepted. Corrected design:

#### Phase enum (what work this run represents)

```python
class Phase(str, Enum):
    implement = "implement"
    review = "review"
    fix = "fix"
```

#### Run status enum (operational state of a run)

```python
class RunStatus(str, Enum):
    queued = "queued"              # created, waiting for dispatch
    running = "running"            # agent actively working
    completed = "completed"        # agent finished (success or error)
    blocked = "blocked"            # dependency not met
    awaiting_input = "awaiting_input"  # needs human/external input
    interrupted = "interrupted"    # runtime crash or timeout
    cancelled = "cancelled"       # manually cancelled
```

#### Task status enum (aggregate state of a task)

```python
class TaskStatus(str, Enum):
    pending = "pending"            # not yet started
    in_progress = "in_progress"    # has an active run
    done = "done"                  # review passed
    blocked = "blocked"            # dependency not met
    escalated = "escalated"        # human_review_required
    cancelled = "cancelled"        # manually cancelled
```

#### Workflow status enum

```python
class WorkflowStatus(str, Enum):
    active = "active"              # has at least one non-terminal task
    completed = "completed"        # all tasks done
    escalated = "escalated"        # at least one task escalated
    cancelled = "cancelled"        # manually cancelled
```

#### Valid combinations (examples)

| Phase | Run Status | Meaning |
|-------|-----------|---------|
| implement | queued | Implementation planned, not yet started |
| implement | running | Agent is implementing |
| implement | completed | Implementation finished |
| review | queued | Waiting for reviewer |
| review | running | Reviewer is working |
| review | completed | Review verdict recorded |
| fix | running | Agent is fixing review findings |
| fix | interrupted | Fix was interrupted by runtime crash |

#### Invariant

> Phase describes **what**. Status describes **where in the lifecycle**. They are always independent dimensions.

---

## Gap 6: Trigger Priority

### Feedback summary
Multiple trigger paths exist but priority is not defined. Watchdog should be recovery-only, not the normal progression path.

### Accepted. Corrected design:

#### Trigger priority (highest to lowest)

| Priority | Trigger | Role | When it fires |
|----------|---------|------|--------------|
| 1 | **Completion event** | Primary progression | Agent run finishes → runtime receives exit signal |
| 2 | **Explicit resume** | Manual recovery | User or admin requests resume of a paused/interrupted workflow |
| 3 | **Watchdog sweep** | Automated recovery | Periodic scan detects stale/orphaned state |
| 4 | **Manual admin retry** | Override | Admin forces a retry, creating a new transition key |

#### Rules

1. **Completion event is the normal path.** All other triggers are recovery or override.
2. **Watchdog never preempts an active run.** It only acts on runs that are stale (no activity for > threshold) or orphaned (completed but no follow-up).
3. **Resume checks before acting.** If a run is already `running`, resume is a no-op. If `interrupted` or `queued`, resume re-dispatches.
4. **All triggers use the same idempotent `try_dispatch_next` function.** The trigger source is logged in the audit entry but does not change the dispatch logic.

#### Watchdog constraints

```python
WATCHDOG_CONSTRAINTS = {
    "min_stale_age_minutes": 60,       # don't touch recent runs
    "max_auto_recoveries_per_run": 3,  # escalate after 3 auto-recoveries
    "sweep_interval_minutes": 15,      # how often watchdog runs
    "is_recovery_only": True,          # never the primary trigger
}
```

#### Invariant

> The watchdog is a safety net, not the engine. Normal workflow progression is driven by completion events. Watchdog only acts when the normal path has failed.

---

## Gap 7: Failure Semantics and Terminal States

### Feedback summary
Failure cases (provider crash, partial output, empty output, duplicate events, conflicting reviews, etc.) and terminal states are not rigorously defined.

### Accepted. Corrected design:

#### Terminal states

| Entity | Terminal states | Meaning |
|--------|---------------|---------|
| **Run** | `completed`, `cancelled` | Run is finished, no further updates |
| **Task** | `done`, `escalated`, `cancelled` | Task will not progress further without external action |
| **Workflow** | `completed`, `escalated`, `cancelled` | Workflow is finished or requires human intervention |

#### Non-terminal states (workflow remains active)

| State | Meaning | Auto-progresses? |
|-------|---------|-----------------|
| `queued` | Waiting for dispatch | Yes, via dispatcher |
| `running` | Agent working | Yes, via completion event |
| `blocked` | Dependency not met | Yes, when dependency resolves |
| `interrupted` | Runtime crash/timeout | Yes, via watchdog recovery |
| `awaiting_input` | Needs external input | No, requires explicit resume |

#### Failure handling matrix

| Failure scenario | Detection | Action |
|-----------------|-----------|--------|
| **Provider crash** (exit_code != 0) | Completion event with non-zero exit | Mark run `completed` with `exit_reason=error`, requeue same phase if retry < threshold, else escalate |
| **Partial output** (no structured handoff) | Completion event, `StructuredRunOutput` is None | Create minimal handoff from runtime-observable data, proceed with transition |
| **Empty output** (no diff, no log) | Completion event, all refs are None | Mark run `completed` with `exit_reason=empty_output`, escalate to `awaiting_input` |
| **Duplicate completion event** | `try_dispatch_next` finds existing transition key | Skip, log "duplicate completion" |
| **Conflicting review records** | Two reviews for same run_id | Accept the first by timestamp, reject the second, log conflict |
| **Missing artifacts** | Reviewer cannot find referenced files | Reviewer writes `verdict=hold` with `reason=missing_artifacts`, run enters `awaiting_input` |
| **Interrupted recovery** | Watchdog detects `interrupted` run | Create new run for same phase, increment retry count |
| **Stale resumption** | Resume request for a run that was already recovered | Idempotent check via transition key, skip if already dispatched |
| **Retry threshold exceeded** | `retry_count >= max_retries` | Task status → `escalated`, workflow status → `escalated` if no other active tasks |

#### Progression invariants

> 1. A workflow remains active until it enters an explicit terminal state (`completed`, `escalated`, `cancelled`).
> 2. A checkpoint report is never a terminal event. Only explicit terminal state transitions end a workflow.
> 3. If the runtime cannot determine the next step, the task enters `awaiting_input`, not silent termination.

---

## Summary of Design Corrections

| Gap | Correction | Impact on existing design doc |
|-----|-----------|------------------------------|
| 1. Layering | 5-layer architecture with explicit ownership | New section in orchestration-engine-design.md |
| 2. Source of truth | Event records = truth, materialized state = cache | Modifies workflow model section |
| 3. Completion handler | Runtime-observable minimum + optional structured output | Corrects completion handler API |
| 4. Idempotency | Transition keys + dispatch-at-most-once | New section, core design rule |
| 5. Phase/status | Separate enums, independent dimensions | Corrects all status/phase references |
| 6. Trigger priority | Completion > resume > watchdog > manual | New section, watchdog is recovery-only |
| 7. Failure/terminal | Explicit terminal states, failure matrix, progression invariants | New section, core design rules |

## Relationship to Implementation

These corrections should be applied to `docs/plans/2026-03-07-orchestration-engine-design.md` before implementation begins. The corrections do not change the overall direction — they make the runtime model precise enough to implement without ambiguity.

The feedback's final assessment is correct: the strategy is sound, the runtime design needed rigor. This document provides that rigor.
