---
doc_version: 1
last_updated: 2026-03-07
status: proposed
depends_on:
  - docs/plans/2026-03-06-workflow-orchestration-mvp.md
  - docs/reports/2026-03-07-agent-orchestration-framework-reference.md
---

# Orchestration Engine Design — Handoff-Driven Workflow Continuity

## Purpose

This document specifies the orchestration engine architecture for B-TWIN.
It extends the existing workflow orchestration MVP plan with:

1. **Handoff record model** — structured agent-to-agent coordination via documents
2. **Continuation context builder** — history-aware context assembly for each workflow step
3. **Dispatcher integration** — how handoffs connect to the transition engine and auto-progression

The design follows B-TWIN's core principle: **document-based coordination, not real-time messaging**.

---

## Design Principles

1. **Documents are the coordination medium** — agents communicate through persisted handoff records, not chat
2. **Headless-first** — all orchestration works through MCP tools and API; dashboard is optional
3. **History-aware dispatch** — continuation context includes relevant past workflows, not just current state
4. **Minimal role model** — planner / implementer / reviewer; no organizational hierarchy
5. **Recovery by default** — any interrupted workflow can resume from persisted documents alone

---

## 1. Handoff Record Model

### 1.1 HandoffRecord

A handoff record is written by an agent when it completes a phase and passes work to the next agent/phase.

```python
class HandoffRecord(BaseModel):
    """Written by the completing agent at phase boundary."""

    handoff_id: str           # rec_<ulid>
    workflow_id: str
    task_id: str
    run_id: str
    from_phase: Phase         # implement | review | fix
    from_agent: str           # agent identifier
    to_phase: Phase           # next expected phase
    created_at: datetime

    # Work summary
    summary: str              # what was done
    changed_files: list[str]  # files touched
    decisions: list[str]      # key decisions made
    open_issues: list[str]    # unresolved items

    # Phase-specific payloads
    review_request: ReviewRequest | None = None   # when handing off to review
    fix_request: FixRequest | None = None         # when handing off to fix
    completion_report: CompletionReport | None = None  # when task is done
```

### 1.2 ReviewRequest (implement → review handoff)

```python
class ReviewRequest(BaseModel):
    """Attached to handoff when requesting review."""

    review_scope: str         # what to review
    acceptance_criteria: list[str]
    test_results: str | None = None
    notes: str | None = None
```

### 1.3 FixRequest (review → fix handoff)

```python
class FixRequest(BaseModel):
    """Attached to handoff when review fails."""

    verdict: Literal["fail", "hold"]
    findings: list[str]       # what was found
    required_fixes: list[str] # what must be fixed
    review_round: int
    severity: Literal["minor", "major", "critical"] = "minor"
```

### 1.4 CompletionReport (task done)

```python
class CompletionReport(BaseModel):
    """Attached to handoff when task is fully complete."""

    final_summary: str
    artifacts: list[str]      # produced outputs
    total_review_rounds: int
    lessons: list[str]        # observations for future reference
```

### 1.5 Storage layout

```
~/.btwin/entries/{project}/workflow/{workflow_id}/
├── epic.md                           # EpicRecord
├── tasks/
│   ├── {task_id}.md                  # TaskRecord
│   └── ...
├── runs/
│   ├── {run_id}.md                   # TaskRunRecord
│   └── ...
└── handoffs/
    ├── {handoff_id}.md               # HandoffRecord (markdown + frontmatter)
    └── ...
```

Handoff records are stored as markdown documents with YAML frontmatter, following the same pattern as all other B-TWIN records. This makes them:
- searchable via `btwin_search`
- indexable by the existing indexer
- recoverable from filesystem
- auditable through standard mechanisms

---

## 2. Continuation Context Builder

The continuation context builder assembles the information bundle that the next agent/phase needs to proceed.

### 2.1 Context bundle structure

```python
class ContinuationContext(BaseModel):
    """Assembled by the runtime for each new agent invocation."""

    # Workflow position
    workflow_goal: str
    current_task: TaskSummary
    current_phase: Phase
    workflow_position: str    # "task 3 of 7, review phase, round 2"

    # Immediate context
    latest_handoff: HandoffRecord
    prior_review_findings: list[str] | None = None
    recent_file_changes: list[str]

    # Historical context (B-TWIN unique)
    similar_past_workflows: list[WorkflowSummary]
    relevant_past_failures: list[str]

    # Instructions
    action_instruction: str   # exact next action
    stop_conditions: list[str]
    escalation_conditions: list[str]
```

### 2.2 History-aware context assembly

This is B-TWIN's key differentiator. The context builder does not just pass forward the current workflow state — it searches for relevant historical context.

```
build_continuation_context(task, phase, handoff):
    1. read workflow goal and task spec
    2. read latest handoff record
    3. read prior review findings (if fix phase)
    4. list recent file changes from handoff
    5. search past workflows:
       - btwin_search(task.title + task.spec, record_type="workflow")
       - filter for completed workflows with similar scope
       - extract review round counts, failure patterns, lessons
    6. assemble action instruction based on phase:
       - implement: "implement {spec}, produce handoff with changed files"
       - review: "review against {criteria}, write review verdict"
       - fix: "fix {required_fixes}, produce new handoff"
    7. attach stop and escalation conditions
    8. return ContinuationContext
```

### 2.3 Similar workflow search

The search uses B-TWIN's existing vector search (ChromaDB) to find semantically similar past tasks:

```python
async def find_similar_past_workflows(
    task: TaskRecord,
    n_results: int = 3,
) -> list[WorkflowSummary]:
    """Search indexed workflow records for similar past work."""
    query = f"{task.title} {task.spec}"
    results = await btwin.search(
        query=query,
        n_results=n_results,
        record_type="workflow",
    )
    return [
        WorkflowSummary(
            task_title=r.metadata.get("title"),
            review_rounds=r.metadata.get("total_review_rounds"),
            outcome=r.metadata.get("status"),
            lessons=r.metadata.get("lessons", []),
        )
        for r in results
        if r.metadata.get("status") == "done"
    ]
```

---

## 3. Dispatcher Integration

### 3.1 Dispatch flow

The dispatcher connects the transition engine (workflow_gate) with the handoff/context system:

```
agent completes phase
    │
    ├── 1. agent writes HandoffRecord
    │      (summary, changed files, review/fix request)
    │
    ├── 2. completion handler receives:
    │      - task_id, run_id, phase, handoff_id
    │
    ├── 3. workflow_gate computes transition:
    │      - implement complete → review queued
    │      - review fail → fix queued
    │      - review pass → task done → next task
    │
    ├── 4. dispatcher creates new TaskRunRecord:
    │      - new run_id, next phase, status=queued
    │
    ├── 5. context builder assembles ContinuationContext:
    │      - reads handoff record
    │      - searches similar past workflows
    │      - builds action instruction
    │
    ├── 6. dispatcher stores context bundle as document:
    │      - persisted so it survives runtime restart
    │
    └── 7. next agent is invoked with context bundle
         (or run stays queued for manual/watchdog pickup)
```

### 3.2 Completion handler API

```
POST /api/workflows/runs/{run_id}/complete
{
    "exit_reason": "success" | "error" | "timeout",
    "handoff": {
        "summary": "...",
        "changed_files": [...],
        "decisions": [...],
        "open_issues": [...],
        "review_request": { ... }   // or fix_request, completion_report
    }
}
```

The completion handler:
1. Persists the handoff record
2. Updates the task run status
3. Calls the transition gate
4. If next step exists, creates the next run and builds context
5. Returns the next action (or "workflow complete" / "escalated")

### 3.3 Recovery from persisted state

If the runtime crashes between step 3 and step 7:
- The handoff record is already persisted (step 1)
- The transition is deterministic from persisted state
- The watchdog/sweep loop re-reads workflow state from documents
- It detects a completed run with no subsequent queued run
- It re-runs steps 3–7

This is the fundamental advantage of document-based coordination: **recovery is just re-reading files**.

---

## 4. MCP Tool Extensions

The orchestration engine exposes new MCP tools for AI clients:

### 4.1 Workflow management tools

| Tool | Purpose |
|------|---------|
| `btwin_create_workflow(goal, tasks)` | Create a new workflow with ordered tasks |
| `btwin_workflow_status(workflow_id?)` | Get current workflow state and next action |
| `btwin_complete_phase(run_id, handoff)` | Complete current phase with handoff record |
| `btwin_search_workflows(query)` | Search past workflows by semantic similarity |

### 4.2 Tool interaction example

```
# Agent receives task via MCP
→ btwin_workflow_status()
← "Task 2 of 5: 'add rate limiter', phase: implement, context: {continuation_context}"

# Agent works on implementation...

# Agent completes phase
→ btwin_complete_phase(run_id="run_abc", handoff={
    summary: "Added rate limiter middleware with sliding window",
    changed_files: ["src/middleware/rate_limiter.py", "tests/test_rate_limiter.py"],
    decisions: ["chose sliding window over fixed window for smoother limiting"],
    review_request: {
        review_scope: "rate limiting logic and test coverage",
        acceptance_criteria: ["tests pass", "handles edge cases"]
    }
  })

# Runtime automatically:
# 1. persists handoff
# 2. transitions to review phase
# 3. builds context with past similar reviews
# 4. queues review run
```

---

## 5. Agent Role Contracts

### 5.1 Planner

- **Input**: user goal or epic description
- **Output**: ordered list of TaskRecords with specs, dependencies, acceptance criteria
- **Writes**: EpicRecord + TaskRecords
- **Does not**: implement or review

### 5.2 Implementer

- **Input**: ContinuationContext with task spec and action instruction
- **Output**: code changes + HandoffRecord with ReviewRequest
- **Writes**: HandoffRecord (implement → review)
- **Reads**: task spec, prior handoffs (if fix phase), similar past implementations

### 5.3 Reviewer

- **Input**: ContinuationContext with handoff summary and review scope
- **Output**: review verdict + HandoffRecord with FixRequest or CompletionReport
- **Writes**: HandoffRecord (review → fix or review → done)
- **Reads**: handoff record, changed files, acceptance criteria, past review patterns

### 5.4 Role assignment

For MVP, role assignment is implicit based on phase:
- `implement` / `fix` phase → implementer role
- `review` phase → reviewer role
- workflow creation → planner role

The same agent can play all roles. Role specialization (dedicated reviewer agent, etc.) is a future extension.

---

## 6. Watchdog and Sweep

### 6.1 Stale run detection

```python
def detect_stale_runs(max_age_minutes: int = 60) -> list[TaskRunRecord]:
    """Find runs that are in_progress but have not been touched recently."""
    all_runs = storage.list_all_task_runs(status="in_progress")
    return [
        run for run in all_runs
        if (now() - run.last_touched_at).minutes > max_age_minutes
    ]
```

### 6.2 Orphaned next-step detection

```python
def detect_orphaned_transitions() -> list[TaskRecord]:
    """Find tasks where a run completed but no next run was created."""
    for task in storage.list_tasks(status="in_progress"):
        runs = storage.list_task_runs(task.task_id)
        latest = max(runs, key=lambda r: r.completed_at or datetime.min)
        if latest.status == "completed" and not any(
            r.status in ("queued", "in_progress") for r in runs
        ):
            yield task  # completed run with no follow-up
```

### 6.3 Sweep action

The sweep loop runs on an internal interval (no external cron for MVP):
1. Detect stale runs → mark as `interrupted`, create recovery run
2. Detect orphaned transitions → re-run transition gate, create next run
3. Detect workflows with `human_review_required` → surface in dashboard / API
4. Log all sweep actions to audit trail

---

## 7. Relationship to Existing Plans

This design extends and refines:

| Existing document | Relationship |
|-------------------|-------------|
| `2026-03-06-workflow-orchestration-mvp.md` | This design adds the handoff model and context builder on top of the MVP's domain models and gate |
| `2026-03-07-dashboard-ui-and-framework-extension-todo.md` | Track B items (B1–B5) implement the models and engine described here |
| `2026-03-07-agent-orchestration-framework-reference.md` | This design realizes the report's recommendation of "our data model + simplified orchestration engine" |

### Implementation order

1. **Workflow domain models** (MVP Task 1) — EpicRecord, TaskRecord, TaskRunRecord
2. **HandoffRecord model** (new) — extends the model layer
3. **Workflow gate** (MVP Task 2) — transition rules
4. **Continuation context builder** (new) — history-aware context assembly
5. **Dispatcher with handoff integration** (MVP Task 6 extended) — completion handler + auto-progression
6. **MCP tool extensions** (new) — btwin_create_workflow, btwin_complete_phase, etc.
7. **Watchdog/sweep** (MVP Task 6 extended) — stale run and orphan detection

---

## 8. What This Design Does NOT Cover

- **Dashboard UI** — covered in `2026-03-07-dashboard-visualization-spec.md`
- **Multi-agent concurrent execution** — MVP uses sequential execution; parallel agents are a future extension
- **External agent providers** — MVP assumes MCP clients; direct provider integration is future work
- **Workflow templates** — reusable workflow patterns are a future extension
- **Cross-project workflows** — MVP is single-project scoped
