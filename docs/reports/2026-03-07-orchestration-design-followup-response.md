---
doc_version: 1
last_updated: 2026-03-07
status: draft
responds_to:
  - docs/reports/2026-03-07-orchestration-design-feedback-followup.md
updates:
  - docs/plans/2026-03-07-orchestration-engine-design.md
---

# Orchestration Design — Follow-up Response (Precision Refinements)

## Purpose

This document addresses the 6 remaining precision gaps identified in the follow-up feedback.
All 6 are accepted. None require architectural changes — they tighten the design for implementation safety.

---

## 1. Review Result Normalization Contract

### Feedback
Review output needs a canonical normalization rule. Without it, the review/fix loop becomes unstable.

### Accepted. Canonical review contract:

```python
class CanonicalReviewResult(BaseModel):
    """Every review completion MUST produce this, regardless of worker output quality."""

    verdict: Literal["pass", "fail", "hold"]
    findings: list[ReviewFinding]
    required_fixes: list[str]       # empty if verdict == pass
    review_round: int
    confidence: Literal["high", "low"] = "high"
```

```python
class ReviewFinding(BaseModel):
    """Single structured finding from a review."""

    category: str                   # e.g. "edge_case", "test_coverage", "security"
    description: str
    severity: Literal["minor", "major", "critical"] = "minor"
    file_ref: str | None = None     # file path if applicable
```

#### Normalization rules

| Worker output state | Normalization action |
|--------------------|--------------------|
| Structured verdict + findings provided | Use directly, validate against schema |
| Verdict provided but findings missing | Accept verdict, set `findings = []`, set `confidence = "low"` |
| Findings provided but no verdict | Infer verdict: any `critical` finding → `fail`, else → `hold` |
| No structured output at all | Set `verdict = "hold"`, `findings = []`, `confidence = "low"`, log warning |
| Conflicting signals (pass + critical findings) | Override to `fail`, log conflict |

#### Invariant

> Review completion always produces a `CanonicalReviewResult`. The workflow engine never reads raw worker output directly — it reads only the normalized result.

---

## 2. TaskRun Lifecycle Clarification

### Feedback
The design implies both immutability and status updates. Implementation needs to know the exact mutability model.

### Accepted. MVP model: "open → closed → immutable"

#### Lifecycle

```
created (open)
    │
    │  mutable fields while open:
    │    - status: queued → running
    │    - last_touched_at
    │
    ▼
closed (immutable)
    │
    │  set once on close:
    │    - status: completed | interrupted | cancelled
    │    - completed_at
    │    - exit_code
    │    - exit_reason
    │    - handoff_id (ref to HandoffRecord)
    │
    └── never modified after close
```

#### Rules

1. A `TaskRunRecord` is **mutable** while `status ∈ {queued, running}`
2. Only `status` and `last_touched_at` may change while open
3. Once `status ∈ {completed, interrupted, cancelled}`, the record is **frozen**
4. Any further state about this run is recorded as a **new event** (e.g., `ReviewRecord`), not as a mutation of the run record

#### Future option (not MVP)

If stronger event purity is needed later, split into `RunStartedEvent` + `RunCompletedEvent`. But the "open then frozen" model is sufficient for MVP and avoids event-join complexity.

---

## 3. `awaiting_input` Boundaries

### Feedback
`awaiting_input` is too broad. Risk of the engine becoming overly conservative and stopping too often.

### Accepted. Strict boundary definitions:

| State | Definition | Who resolves it | Auto-recoverable? |
|-------|-----------|-----------------|-------------------|
| `blocked` | A prerequisite task is not yet `done` | Workflow engine (auto-unblocks when dependency completes) | **Yes** |
| `interrupted` | Execution stopped unexpectedly (crash, timeout, network) | Watchdog (auto-creates recovery run) | **Yes** |
| `awaiting_input` | Runtime cannot safely determine next step without human clarification | Human (explicit resume via API/CLI) | **No** |
| `escalated` | Retry/review threshold exceeded, requires human judgment on whether to continue | Human (explicit decision via API/CLI) | **No** |

#### When to use `awaiting_input` (exhaustive list for MVP)

1. Review verdict is `hold` (reviewer explicitly requested human input)
2. Worker output is completely empty AND no diff/artifact is detectable
3. Task spec references external resource that is unavailable
4. Conflicting review results that normalization cannot resolve automatically

#### When NOT to use `awaiting_input`

- Missing structured output → normalize with defaults, proceed (not `awaiting_input`)
- Non-zero exit code → `interrupted`, let watchdog retry (not `awaiting_input`)
- Review `fail` → create fix run (not `awaiting_input`)
- Dependency not met → `blocked` (not `awaiting_input`)

#### Invariant

> `awaiting_input` is used only when the runtime cannot safely infer the next step without external clarification. When in doubt, prefer `interrupted` (auto-recoverable) over `awaiting_input` (requires human).

---

## 4. MVP Linearity Scope Statement

### Feedback
The design implies linear progression but doesn't state this explicitly. Risk of scope creep.

### Accepted. Explicit scope statement:

> **MVP Scope Statement**
>
> The MVP workflow engine assumes predominantly sequential task progression:
> - Tasks within a workflow are ordered and executed one at a time
> - Each task follows a linear phase cycle: implement → review → (fix → review)* → done
> - The next task begins only after the previous task reaches a terminal state
> - Task dependencies are limited to simple predecessor ordering (`depends_on` = previous task)
>
> **Explicitly out of scope for MVP:**
> - DAG-based task scheduling
> - Parallel task execution (fan-out)
> - Merge barriers (fan-in / join)
> - Conditional branching based on runtime results
> - Cross-workflow dependencies
> - Sub-workflow nesting
>
> These capabilities may be added in future phases but are not part of the initial implementation.

#### Why sequential is enough for MVP

The primary problem being solved is **continuity** — making sure step N+1 happens after step N without a new user message. Sequential ordering solves this. Parallelism and DAG scheduling are optimization problems that can be layered on after the core continuity loop is proven.

---

## 5. Continuation Context Builder Contract

### Feedback
The context builder is one of the most important runtime components but its input/output contract is too implicit.

### Accepted. Concrete contract:

#### Inputs (all from persisted state)

```python
class ContextBuilderInput(BaseModel):
    """Everything the context builder reads to assemble a prompt bundle."""

    # Workflow level
    workflow_goal: str
    workflow_position: str          # "task 3 of 7"

    # Task level
    task_title: str
    task_spec: str
    task_acceptance_criteria: list[str]
    task_dependencies_met: bool

    # Run level
    target_phase: Phase             # implement | review | fix
    retry_count: int

    # Handoff chain
    latest_handoff: HandoffRecord | None
    latest_review: CanonicalReviewResult | None
    unresolved_fixes: list[str]

    # Artifacts
    recent_file_changes: list[str]
    diff_ref: str | None
    log_ref: str | None

    # Historical (B-TWIN unique)
    similar_past_tasks: list[PastTaskSummary]
```

#### Outputs (phase-specific prompt bundles)

```python
class ImplementerBundle(BaseModel):
    """Context for an implement or fix phase."""

    system_context: str             # workflow goal, position, task spec
    action_instruction: str         # "implement X" or "fix Y based on review findings"
    acceptance_criteria: list[str]
    prior_decisions: list[str]      # from handoff chain
    historical_notes: list[str]     # lessons from similar past tasks
    stop_conditions: list[str]
    handoff_template: str           # what the agent should produce on completion

class ReviewerBundle(BaseModel):
    """Context for a review phase."""

    system_context: str
    review_scope: str               # from handoff's review_request
    acceptance_criteria: list[str]
    changed_files: list[str]
    prior_review_history: list[str] # previous rounds if any
    historical_patterns: list[str]  # common failure patterns for similar tasks
    verdict_template: str           # expected output format
```

#### Builder behavior

```
build_context(input: ContextBuilderInput) -> ImplementerBundle | ReviewerBundle:

    1. select output type based on target_phase:
         implement, fix → ImplementerBundle
         review → ReviewerBundle

    2. assemble system_context from workflow_goal + task_title + position

    3. if target_phase == implement:
         action = f"Implement: {task_spec}"
         include acceptance_criteria
    elif target_phase == fix:
         action = f"Fix these review findings: {unresolved_fixes}"
         include latest_review findings
    elif target_phase == review:
         action = f"Review: {latest_handoff.review_request.review_scope}"
         include changed_files from handoff

    4. attach historical context:
         for similar in similar_past_tasks:
           if similar has lessons → add to historical_notes/patterns
           if similar had many review rounds → add warning

    5. attach stop_conditions:
         - "stop if blocked by external dependency"
         - "stop if task scope changes beyond spec"
         - f"escalate if review round > {MAX_ROUNDS}"

    6. return assembled bundle
```

#### Invariant

> The continuation context builder is deterministic: given the same persisted workflow state and runtime artifacts, it always produces the same prompt bundle. It has no hidden state and no side effects.

---

## 6. Transition Examples

### Feedback
Concrete examples reduce ambiguity for implementers.

### Accepted. Six canonical transition scenarios:

#### Example 1: Implement success → review queued

```
State before:
  task-1: status=in_progress
  run-1:  phase=implement, status=running

Event:
  RunCompletionEvent(run_id=run-1, exit_code=0)
  StructuredRunOutput(summary="Added auth module", review_request={...})

Actions:
  1. persist HandoffRecord(from_phase=implement, to_phase=review)
  2. freeze run-1: status=completed
  3. workflow_engine.compute_next → NextStep(phase=review)
  4. create run-2: phase=review, status=queued
  5. record transition_key: "task-1:run-1:implement:completed→review:queued"
  6. context builder → ReviewerBundle
  7. dispatch run-2

State after:
  task-1: status=in_progress
  run-1:  phase=implement, status=completed (frozen)
  run-2:  phase=review, status=queued → running
```

#### Example 2: Review fail → fix queued

```
State before:
  run-2: phase=review, status=running

Event:
  RunCompletionEvent(run_id=run-2, exit_code=0)
  StructuredRunOutput(verdict=fail, findings=[{category:"edge_case", ...}])

Actions:
  1. normalize → CanonicalReviewResult(verdict=fail, ...)
  2. persist ReviewRecord
  3. freeze run-2: status=completed
  4. workflow_engine.compute_next → NextStep(phase=fix)
  5. create run-3: phase=fix, status=queued, retry_count=1
  6. record transition_key
  7. context builder → ImplementerBundle (fix mode)
  8. dispatch run-3

State after:
  run-2: phase=review, status=completed (frozen)
  run-3: phase=fix, status=queued → running
```

#### Example 3: Fix success → review queued (round 2)

```
State before:
  run-3: phase=fix, status=running

Event:
  RunCompletionEvent(run_id=run-3, exit_code=0)

Actions:
  1. persist HandoffRecord(from_phase=fix, to_phase=review)
  2. freeze run-3
  3. compute_next → NextStep(phase=review)
  4. create run-4: phase=review, status=queued, review_round=2
  5. record transition_key
  6. dispatch run-4

State after:
  run-3: phase=fix, status=completed (frozen)
  run-4: phase=review, status=queued → running
```

#### Example 4: Duplicate completion event → skipped

```
State before:
  run-1: phase=implement, status=completed (already processed)
  run-2: phase=review, status=running (already dispatched)

Event:
  RunCompletionEvent(run_id=run-1, exit_code=0)  # duplicate

Actions:
  1. try_dispatch_next(run_id=run-1)
  2. check transition_key: "task-1:run-1:implement:completed→review:queued" EXISTS
  3. return DispatchResult(status="already_dispatched", skipped=True)
  4. log: "duplicate completion event for run-1, skipped"

State after:
  no change
```

#### Example 5: Interrupted run → watchdog recovery

```
State before:
  run-2: phase=review, status=running, last_touched_at=90min ago

Trigger:
  watchdog sweep detects stale run (> 60min threshold)

Actions:
  1. mark run-2: status=interrupted, exit_reason="watchdog_stale"
  2. freeze run-2
  3. check auto_recovery_count for task-1: 1 (< max 3)
  4. create run-5: phase=review, status=queued (same phase, recovery)
  5. record transition_key with "recovery" suffix
  6. dispatch run-5
  7. audit: "watchdog recovered stale run-2, created run-5"

State after:
  run-2: phase=review, status=interrupted (frozen)
  run-5: phase=review, status=queued → running
```

#### Example 6: Retry threshold exceeded → escalation

```
State before:
  task-1: retry_count=3, max_retries=3
  run-8: phase=review, status=running

Event:
  RunCompletionEvent(run_id=run-8, exit_code=0)
  CanonicalReviewResult(verdict=fail, findings=[...])

Actions:
  1. persist ReviewRecord
  2. freeze run-8
  3. workflow_engine.compute_next:
       retry_count (3) >= max_retries (3) → escalate
  4. task-1: status=escalated
  5. check other active tasks: none → workflow: status=escalated
  6. NO new run created
  7. audit: "task-1 escalated after 3 review failures"

State after:
  task-1: status=escalated (terminal)
  workflow: status=escalated (terminal)
  dashboard shows: "HUMAN REVIEW REQUIRED"
```

---

## Summary

All 6 precision gaps addressed:

| # | Gap | Resolution |
|---|-----|-----------|
| 1 | Review normalization | `CanonicalReviewResult` with 5-case normalization table |
| 2 | TaskRun lifecycle | "open → closed → immutable" with explicit mutable/frozen rules |
| 3 | `awaiting_input` boundaries | Exhaustive list of 4 valid uses, strict separation from blocked/interrupted/escalated |
| 4 | MVP linearity | Explicit scope statement with 6 out-of-scope items |
| 5 | Context builder contract | Typed input/output models, deterministic builder algorithm |
| 6 | Transition examples | 6 canonical scenarios covering normal flow, dedup, recovery, escalation |

## Assessment

The feedback is correct: the architecture direction is sound, these are precision refinements. With these additions, the design is implementation-ready. The next step is to consolidate all corrections into the orchestration engine design document and begin implementation planning.
