---
doc_version: 1
last_updated: 2026-03-07
status: draft
---

# Feedback on Agent Orchestration Framework Reference Report

## Target Document
- `docs/reports/2026-03-07-agent-orchestration-framework-reference.md`

## Overall Verdict
The report is directionally strong and useful as a reference document.
It identifies the correct core problem:

- the issue is not only memory persistence,
- the larger gap is the absence of a runtime orchestration layer that turns one completed step into the next workflow step.

It also makes a good strategic distinction:
- do **not** copy Claw-Empire wholesale,
- do borrow its orchestration-continuity mechanisms,
- keep our own strengths in durable, searchable workflow records.

However, before this evolves into a formal design basis, several parts should be clarified and strengthened.

---

## What the Report Gets Right

### 1. Correct problem framing
The report correctly identifies the failure mode we care about:
- user issues a multi-step instruction,
- one task completes,
- a report is sent,
- the workflow stops instead of continuing.

This is the right problem statement.
The report also correctly frames the cause as an orchestration/runtime gap rather than simply a "memory problem."

### 2. Correct extraction from Claw-Empire
The report pulls the right categories from Claw-Empire:
- execution session tracking,
- completion handler,
- next-step dispatcher,
- review/fix loop state machine,
- continuation-context rebuilding,
- watchdog/sweep recovery.

These are the most relevant ideas for solving continuity in our own system.

### 3. Good strategic positioning for our stack
The report correctly positions our likely strengths as:
- durable records,
- searchable workflow state,
- structured metadata,
- auditability,
- recovery-friendly persistence.

This is the right contrast versus a more execution-heavy system like Claw-Empire.

---

## Main Gaps to Address Before Treating This as Design Guidance

### 1. Layering is still too blurred
The report strongly implies that the MCP server/runtime should absorb many concerns at once:
- session tracking,
- workflow persistence,
- next-step dispatch,
- recovery,
- review/fix orchestration,
- provider-specific execution adaptation.

That direction may be valid, but the report does not clearly separate architectural layers.

### Why this matters
If we do not separate concerns now, implementation will likely create a monolithic runtime module.
That would make future debugging and extension much harder.

### Recommended clarification
The follow-up design should explicitly separate at least these layers:

1. **MCP/API ingress layer**
   - receives requests, external events, and control actions
2. **Workflow engine**
   - owns workflow state transitions and next-step computation
3. **Persistence layer**
   - stores workflow/task/run/review/audit records
4. **Execution adapter layer**
   - invokes provider-specific workers / sessions / subagents
5. **Watchdog / sweep loop**
   - performs recovery scans and idempotent redispatch checks

Without this separation, the phrase "add it to the MCP server" is too coarse and will create design ambiguity.

---

### 2. Source of truth is not defined clearly enough
The report proposes useful entities:
- workflow
- task
- task run
- review record

But it does not define which records are:
- raw event facts,
- stored summaries,
- derived/materialized state,
- recomputable views.

### Why this matters
Without this distinction, recovery and dispatcher logic become inconsistent.
The system will not know whether to trust current status fields or recompute them.

### Questions the design must answer
- Is `task.status` authoritative, or derived from latest `task_run` + review records?
- Is `workflow.current_step` stored, derived, or both?
- Does recovery rebuild state from raw events or trust materialized state first?
- Which records are append-only, and which are mutable summaries?

### Recommended direction
A stronger model would separate:
- **event records**: task runs, review records, transition/audit entries
- **materialized summaries**: task.status, workflow.status, current_step, next_step
- **recovery behavior**: trust summaries first, but allow recomputation from event records when needed

---

### 3. Completion handler design is slightly too optimistic
The report describes completion handler inputs such as:
- `result_summary`
- `artifacts`
- `updated_files`
- optional review findings

This is useful conceptually, but it assumes structured completion data is reliably available.
In practice, provider outputs may be inconsistent.

### Why this matters
A completion handler should be based first on what the runtime can observe reliably, not on what the model may or may not provide in a structured way.

### Recommended correction
The minimum completion handler input should be framed around runtime-observable facts:
- `task_id`
- `run_id`
- `phase`
- `exit_code`
- `started_at`
- `completed_at`
- `stdout/stderr or log reference`
- `diff or artifact reference if available`
- optional `structured_output_ref`

This makes the design robust even when providers do not return ideal structured outputs.

---

### 4. Idempotency is missing as a first-class requirement
The report proposes a dispatcher and sweep/watchdog logic, but it does not make idempotency explicit.

### Why this matters
If multiple triggers can advance the workflow, duplicate dispatch becomes a major risk.
Possible competing triggers include:
- completion event,
- resume request,
- watchdog recovery,
- manual admin retry.

Without idempotent transition handling, the system can create duplicate review runs or duplicate next tasks.

### Required addition
The next design document should explicitly require:
- idempotent transitions,
- transition locks or transition keys,
- "dispatch at most once" semantics for each computed next step,
- duplicate completion-event tolerance.

### Strong recommendation
Add a design invariant such as:

> Workflow next-step computation may run multiple times, but each transition must be dispatched at most once.

This should be treated as a core design rule, not an implementation detail.

---

### 5. The phase model should be separated from the status model
The report correctly introduces phases like:
- implement
- review
- fix
- done

But phase and status are still not clearly separated.

### Why this matters
A task can be in the same phase but in different operational states.
For example:
- phase=`review`, status=`queued`
- phase=`review`, status=`running`
- phase=`review`, status=`blocked`
- phase=`review`, status=`awaiting_input`

If phase and status are conflated, edge-case handling becomes messy.

### Recommended model
Separate:
- **phase** = what kind of work this run represents
- **status** = what operational state that work is currently in

Example:
- `phase`: `implement | review | fix`
- `status`: `queued | running | completed | blocked | awaiting_input | escalated | cancelled`

This separation will make the workflow engine more coherent.

---

### 6. Trigger priority should be defined explicitly
The report correctly introduces multiple ways a next step could begin:
- completion event,
- resume API,
- watchdog/sweep loop.

But it does not define trigger priority.

### Why this matters
If multiple trigger paths are valid, the runtime must know which one is the primary path and which ones are only for recovery.

### Recommended priority
1. **completion event trigger**
2. **explicit resume trigger**
3. **watchdog recovery trigger**
4. **manual admin trigger**

Also, watchdog should be described as a recovery mechanism, not the normal progression mechanism.

---

### 7. Failure semantics and terminal states are underdefined
The report does mention some guardrails, but does not yet define failure semantics rigorously enough.

### Missing areas
The design still needs explicit handling for:
- provider crash,
- partial output,
- empty output,
- duplicate completion events,
- conflicting review records,
- missing artifacts,
- interrupted recovery,
- stale resumptions.

### Terminal states should be explicit
The next design should clearly define which workflow/task states are terminal.
Suggested examples:
- `done`
- `cancelled`
- `human_review_required`
- `awaiting_input`

This is especially important because one of the central goals is to stop treating ordinary checkpoint reports as terminal.

A strong invariant should be added:

> A workflow remains active until it enters an explicit terminal state.

---

## Guidance on Scope

### Good decision already present
The report is correct to avoid directly importing all of Claw-Empire's organizational constructs.
Using a minimal role model first is the right move.

### Recommended MVP role model
Rather than using departments, leaders, and meetings from the start, MVP should likely begin with just:
- planner
- implementer
- reviewer

Even better, these should be treated as **run roles**, not necessarily as fixed agent identities.
The same worker/provider could play different roles across runs.

This gives us:
- less architectural weight,
- more flexibility,
- less premature commitment to organization metaphors.

---

## Suggested Additions to the Next Design Document
The follow-up design document should add sections for:

### 1. Architectural layers
Explicit layer diagram and ownership split.

### 2. State source of truth
Clarify event records vs materialized state vs recomputed views.

### 3. Idempotency model
Define transition keys, duplicate protection, and dispatch-at-most-once semantics.

### 4. Failure semantics
Describe what happens for all key failure and recovery edge cases.

### 5. Terminal states and progression invariants
Make it impossible to interpret checkpoint reporting as silent workflow termination.

### 6. Trigger ordering
Completion event is primary, watchdog is recovery-only.

---

## Final Assessment
The reference report is a good and useful strategic document.
It is strong enough to justify the direction:
- keep our durable memory/data model,
- add a lightweight but explicit orchestration engine inspired by Claw-Empire.

However, it is not yet sufficient as a detailed design basis.
Before implementation, the next document should make the runtime model more precise in these areas:
- layering,
- source of truth,
- idempotency,
- phase vs status separation,
- trigger priority,
- failure/terminal semantics.

## Bottom line
The current report is good strategy.
The next document must be rigorous runtime design.
