---
doc_version: 1
last_updated: 2026-03-07
status: draft
---

# Agent Orchestration Framework Reference Report

## Purpose
This report summarizes:

1. why our current event-driven interaction model is insufficient for long multi-step work,
2. what minimum orchestration features should be added around our MCP server/runtime,
3. how that direction compares with the reference project **Claw-Empire**,
4. the trade-offs, strengths, and weaknesses of each approach.

The core problem is not memory storage alone.
The deeper problem is that an LLM worker is typically invoked per event/turn, so without a runtime framework that explicitly persists state and dispatches the next step, multi-step workflows tend to stop after a partial completion report.

---

## Problem Statement

### Current failure pattern
A user issues a request containing multiple tasks, often including a review/fix cycle.

Example shape:
- implement task A
- review A
- fix A
- then continue with task B
- finally produce an integrated result

What happens today in the failure case:
1. the agent completes task A,
2. reports progress,
3. the runtime treats that completion/report as the end of the flow,
4. the next task is not automatically continued unless a new user event arrives.

### Why this happens
The worker model is fundamentally event-driven:
- request comes in,
- model runs,
- model returns,
- run ends.

If the runtime does not persist workflow state and explicitly trigger the next step, continuity depends too heavily on prompt memory and chat context.
That is not reliable enough for implementation → review → fix → continue chains.

---

## Key Insight
To support true multi-step work, the system must treat:

- **task completion** as a **workflow transition event**, not as a terminal event,
- **review/fix loops** as **explicit state transitions**, not as informal conversation,
- **continuation** as something rebuilt by the runtime from stored metadata and context, not something assumed to remain in the model's short-term memory.

In short:

> Long-running multi-agent work requires an orchestration runtime, not only a memory store.

---

## Minimum Framework Features We Should Add

### 1. Workflow state model
We need a first-class workflow state model around the MCP runtime.

#### Minimum entities

##### Workflow
- `workflow_id`
- `goal`
- `project_id`
- `project_path`
- `project_context`
- `status`
- `current_step`
- `next_step`
- `created_at`
- `updated_at`

##### Task
- `task_id`
- `workflow_id`
- `title`
- `spec`
- `order`
- `status`
- `assigned_agent`
- `depends_on`
- `review_required`
- `retry_count`

##### Task Run
- `run_id`
- `task_id`
- `phase` (`implement | review | fix`)
- `status`
- `agent_id`
- `provider`
- `session_id`
- `started_at`
- `completed_at`
- `exit_reason`

##### Review Record
- `review_id`
- `task_id`
- `run_id`
- `review_round`
- `verdict` (`pass | fail | hold`)
- `findings`
- `required_fixes`

#### Why this is required
Without these entities, the runtime cannot reliably answer:
- what is currently in progress,
- what was just completed,
- whether we are in implement/review/fix,
- what the next step is,
- whether the workflow is done or merely checkpointed.

---

### 2. Execution session tracking
We should add a lightweight execution-session layer for each task run.

#### Minimum fields
- `session_id`
- `task_id`
- `agent_id`
- `provider`
- `opened_at`
- `last_touched_at`

#### Why this matters
This distinguishes:
- a new task,
- a resumed task,
- a retried review/fix iteration.

It also gives the runtime a stable anchor for pause/resume/continuation behavior.

---

### 3. Completion handler
We need a server-side completion handler triggered when an agent run finishes.

#### Input
- `task_id`
- `run_id`
- `phase`
- `exit_code`
- `result_summary`
- `artifacts`
- `updated_files`
- optional review findings / structured output

#### Responsibilities
1. mark the current run complete,
2. update task/workflow state,
3. persist outputs and audit records,
4. calculate the next step,
5. dispatch the next run if appropriate.

#### Why this is the critical pivot
Today, a completion message often behaves like a stop condition.
With a completion handler, completion becomes an event that advances the workflow.

---

### 4. Next-step dispatcher
We need a dispatcher that decides what happens after each run.

#### Minimum transition rules
- `implement complete -> review queued`
- `review fail -> fix queued`
- `fix complete -> review queued`
- `review pass -> task done`
- `task done + next task exists -> next task implement queued`
- `all tasks done -> workflow done`

#### Additional guardrails
- retry threshold exceeded -> `human_review_required`
- blocked dependency -> `blocked`
- missing context or approval -> `awaiting_input`

#### Why this is necessary
This is the feature that prevents the system from stopping after the first sub-result.

---

### 5. Continuation context builder
We need a runtime component that rebuilds the right context bundle for the next invocation.

#### Bundle should include
- workflow goal
- current task summary
- prior run summary
- unresolved review findings
- recent file changes
- current workflow position
- exact next action instruction
- stop / escalation conditions

#### Why this matters
The model is not continuously thinking in the background.
If we want true continuity, the runtime must reconstruct and re-inject the continuity bundle on every next run.

---

### 6. Review/fix state machine
We should model review/fix as explicit workflow phases.

#### Minimum phases
- `implement`
- `review`
- `fix`
- `review`
- `done`

#### Extra state
- `review_round`
- `retry_count`
- `last_verdict`
- `required_fixes`
- `escalation_state`

#### Why this matters
Without this state machine, the review loop remains an informal chat pattern and is easy to break after a partial report.

---

### 7. Resume / watchdog / sweep loop
We need runtime mechanisms for continuity when execution is interrupted or a next step is not dispatched correctly.

#### Resume API
- resume paused/interrupted task runs,
- restart a pending continuation,
- re-enter a review/fix loop.

#### Watchdog
- detect stuck `in_progress` runs,
- detect orphaned sessions,
- detect workflows with a pending next step but no active runner.

#### Sweep loop
- periodically scan workflow state,
- dispatch missing next-step runs,
- recover or escalate stale workflows.

#### Important note
This does not need an external cron at first.
An internal runtime interval/watchdog loop is enough for MVP.

---

### 8. Audit + checkpoint reporting
We should persist every meaningful transition.

#### Persist
- run started
- run completed
- review failed
- fix queued
- next task unlocked
- workflow escalated
- workflow completed

#### Principle
A progress report should be stored as a checkpoint, not treated as the end of the workflow unless the workflow is truly done.

---

## Event Model We Need
The runtime should move from a mostly chat-event-driven model to a broader orchestration event model.

### Relevant event types
- `user_request_received`
- `task_run_started`
- `task_run_completed`
- `review_verdict_recorded`
- `next_step_ready`
- `resume_requested`
- `watchdog_detected_stale_run`
- `workflow_completed`
- `workflow_escalated`

### Key design point
The next step should be triggered by **runtime events**, not only by new user messages.

---

## Why the MCP Server Is the Right Layer
We already have a data management strategy.
We already plan to persist workflow-related information in structured documents/records.

What is missing is the orchestration engine.

The MCP server/runtime is the right layer for that because it can:
- manage execution sessions,
- persist workflow transitions,
- build continuation bundles,
- dispatch the next worker invocation,
- expose resume/review/recovery APIs,
- keep provider-specific execution logic behind a common interface.

In other words:
- **memory/data stays in our system design**,
- **workflow continuity logic belongs in the MCP runtime/orchestration layer**.

---

# Comparison with Claw-Empire

## High-level difference

### Claw-Empire
Claw-Empire is strongly oriented around **execution orchestration**:
- task/subtask routing,
- team-lead delegation,
- review rounds,
- worktree isolation,
- runtime callbacks/watchdogs,
- explicit next-step advancement.

### Our intended direction
Our system is stronger on **memory, records, and searchable state**:
- structured documents,
- metadata conventions,
- indexability,
- recovery-friendly persistence,
- shared workflow/dashboard foundation.

### Practical interpretation
- Claw-Empire is stronger at **keeping work moving**.
- Our direction can be stronger at **making work durable, searchable, and auditable**.

---

## Comparison from the agent collaboration perspective

### Claw-Empire strengths
1. **Explicit orchestration flow**
   - CEO -> planning -> department leaders -> agents
   - meeting -> delegation -> execution -> review -> approval

2. **Next-step execution logic exists in runtime**
   - completion handling
   - callback queues
   - review-round transitions
   - watchdog/sweep recovery

3. **Strong task isolation**
   - worktree-based execution
   - project-bound task runs
   - task/session ownership

4. **Well-suited for chained work**
   - one task completes,
   - next task or review state is explicitly advanced.

### Claw-Empire weaknesses
1. **Heavy runtime complexity**
   - many coordination constructs,
   - more moving parts to debug,
   - harder to keep simple.

2. **Organizational model may be overbuilt for us**
   - team-lead/department/meeting structures may be more than we need initially.

3. **Central orchestration burden is high**
   - strong dependency on runtime health and orchestration correctness.

---

## Comparison from the memory / context management perspective

### Claw-Empire strengths
1. **Strong operational context**
   - project path / project context
   - task continuation context
   - recent changes
   - session-level continuity

2. **Good re-entry context for active work**
   - enough metadata to resume a task after interruption.

### Claw-Empire weaknesses
1. **Long-term knowledge memory is not the primary design center**
   - it is more operational memory than semantic/knowledge memory.

2. **State is spread across multiple layers**
   - DB rows,
   - runtime maps,
   - logs,
   - meeting minutes,
   - reports.

### Our direction strengths
1. **Stronger durable-state design potential**
   - workflow docs,
   - searchable records,
   - structured metadata,
   - indexer integration,
   - recovery via persisted state.

2. **Better long-term audit and retrieval potential**
   - easier to answer later:
     - what happened,
     - why it happened,
     - what was decided,
     - what remains.

### Our direction weaknesses
1. **Current orchestration continuity is underpowered**
   - memory exists,
   - but continuation is not yet strongly automated.

2. **Data-first architecture alone does not continue execution**
   - persisted memory is necessary,
   - but it does not itself dispatch the next step.

---

# What We Should Borrow from Claw-Empire

## Borrow directly
1. execution session tracking
2. completion handler
3. next-step dispatcher
4. review/fix loop state machine
5. continuation context builder
6. watchdog / sweep recovery

## Borrow carefully / in simplified form
1. organizational hierarchy
2. team-leader meeting system
3. rich department routing model

These are useful references, but likely too heavy for an initial version of our framework.

---

# Recommended Direction

## Recommended architecture
Keep:
- our memory/data/document/indexing strategy,
- our workflow-record model,
- our recovery-friendly persistence.

Add:
- runtime completion hooks,
- next-step dispatcher,
- execution session layer,
- structured review/fix loop,
- watchdog/resume logic in the MCP server runtime.

## In one sentence
We should not copy Claw-Empire wholesale.
We should build:

> **our document- and memory-centered workflow system, plus a Claw-Empire-like orchestration engine for continuity.**

---

# Advantages of Our Intended Approach

## Advantages
1. **Better searchable history and auditability**
2. **Cleaner integration with our existing memory/data strategy**
3. **Potentially simpler role model at MVP**
   - planner / implementer / reviewer can be enough initially
4. **Provider-agnostic orchestration around MCP**
5. **Stronger recovery via persisted workflow records**

## Risks
1. **If we underbuild the runtime dispatcher, continuity still fails**
2. **If everything becomes document-heavy, execution can feel slow/over-ceremonial**
3. **If MCP runtime takes on too much at once, it can become monolithic**

---

# Suggested MVP Scope

## Phase 1 — Core continuity engine
- workflow/task/task-run models
- execution session tracking
- completion handler
- next-step dispatcher
- implement/review/fix/done state machine

## Phase 2 — Recovery and hardening
- structured review findings storage
- retry threshold + human review required
- resume API
- watchdog/sweep loop

## Phase 3 — Visibility and operations
- dashboard visibility for workflow state
- audit/recovery views
- richer planner/reviewer role assignment

---

# Final Conclusion
The main gap in our system is not the lack of memory persistence.
The main gap is the lack of a runtime orchestration layer that turns completion into the next workflow transition.

Claw-Empire is a strong reference because it shows how to solve:
- chained execution,
- review/fix continuity,
- interrupted run recovery,
- next-step dispatch,
- multi-agent progression without requiring a fresh user message for every step.

However, our best path is not to replicate its full organizational framework.
Our best path is to combine:

- **our stronger data/memory model**, with
- **a simplified but explicit orchestration engine in the MCP runtime**.

That gives us a workflow system that is both:
- operationally continuous,
- and durably searchable/recoverable.
