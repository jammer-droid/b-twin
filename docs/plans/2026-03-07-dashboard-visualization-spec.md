---
doc_version: 1
last_updated: 2026-03-07
status: proposed
depends_on:
  - docs/plans/2026-03-07-orchestration-engine-design.md
  - docs/plans/2026-03-07-dashboard-ui-and-framework-extension-todo.md
  - docs/reports/2026-03-07-agent-orchestration-framework-reference.md
---

# Dashboard Visualization Spec — Operational Views for Document-Based Workflows

## Purpose

This document specifies the dashboard views that expose B-TWIN's document-based workflow state.

The core premise: **B-TWIN records everything as searchable documents. The dashboard makes those documents visible and navigable.**

This is not a simulation or a decorative interface. It is an operational dashboard that shows:
- where work is in the pipeline
- what handoffs happened between agents
- where things are blocked or escalated
- what patterns emerge from historical data

---

## Design Principles

1. **Show the documents** — every visual element maps to a persisted record (handoff, task run, review, audit entry)
2. **No hidden state** — the dashboard does not create or own state; it reads from the same storage/API that MCP tools and CLI use
3. **Operational, not decorative** — closer to Linear or Grafana than to a game UI
4. **Progressive disclosure** — overview first, drill into details on demand
5. **Works without the dashboard** — all information is accessible via API and CLI; the dashboard is a convenience layer

---

## View 1: Pipeline View (Primary)

### Purpose
Show all active workflows with their tasks flowing through the implement → review → fix → done pipeline.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Workflow: "API Refactoring"                    ⚡ 3/7 tasks    │
│  created: 2026-03-07  status: in_progress                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  IMPLEMENT        REVIEW          FIX           DONE            │
│  ┌──────────┐                                   ┌──────────┐   │
│  │ Task 5   │                                   │ Task 1   │   │
│  │ error    │                                   │ auth     │   │
│  │ handling │     ┌──────────┐                  │ module ✓ │   │
│  │          │     │ Task 4   │                  └──────────┘   │
│  │ agent-A  │     │ logging  │                  ┌──────────┐   │
│  └──────────┘     │ round 2  │   ┌──────────┐  │ Task 2   │   │
│                   │          │   │ Task 3   │   │ rate     │   │
│                   │ agent-B  │   │ caching  │   │ limiter ✓│   │
│                   └──────────┘   │          │   └──────────┘   │
│                                  │ agent-A  │                   │
│  ░░░░░░░░░░                      └──────────┘                   │
│  Task 6, 7                                                      │
│  (queued)                                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Task card contents
- Task title (truncated)
- Current phase badge
- Assigned agent
- Review round indicator (if > 1)
- Blocker/escalation badge (if applicable)

### Interactions
- Click task card → opens Task Detail view
- Click workflow header → opens Workflow Summary
- Filter by status: all / active / blocked / done

### Data source
- `GET /api/workflows/epics` → workflow list
- `GET /api/workflows/tasks?epic_id={id}` → tasks per workflow
- `GET /api/workflows/runs?task_id={id}` → current run status

---

## View 2: Handoff Timeline

### Purpose
Show the chronological sequence of agent-to-agent handoffs within a workflow, making the collaboration history visible.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Workflow: "API Refactoring" — Handoff Timeline                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ─── 14:32 ─── Task 1: auth module ────────────────────────     │
│  │                                                              │
│  │  ● agent-A → review                                          │
│  │  "Implemented JWT auth with refresh token rotation"           │
│  │  changed: auth.py, middleware.py, tests/test_auth.py          │
│  │  decisions: chose RS256 over HS256 for key rotation           │
│  │                                                              │
│  ─── 15:10 ─────────────────────────────────────────────────     │
│  │                                                              │
│  │  ● agent-B → fix  [verdict: FAIL]                            │
│  │  findings: missing token expiry edge case                     │
│  │  required: add test for expired refresh token                 │
│  │                                                              │
│  ─── 15:45 ─────────────────────────────────────────────────     │
│  │                                                              │
│  │  ● agent-A → review                                          │
│  │  "Added expired token test and fixed expiry check"            │
│  │  changed: auth.py, tests/test_auth.py                         │
│  │                                                              │
│  ─── 16:02 ─────────────────────────────────────────────────     │
│  │                                                              │
│  │  ● agent-B → done  [verdict: PASS]                           │
│  │  "All criteria met, tests pass"                               │
│  │                                                              │
│  ─── 16:03 ─── Task 2: rate limiter ───────────────────────     │
│  │                                                              │
│  │  ● agent-A → review                                          │
│  │  "Added sliding window rate limiter middleware"                │
│  │  ...                                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key elements
- **Timestamp** — when each handoff occurred
- **Direction indicator** — who handed off to which phase
- **Summary** — brief description from the handoff record
- **Verdict badge** — PASS / FAIL / HOLD for review handoffs
- **Changed files** — collapsible list
- **Decisions** — key choices surfaced from handoff records

### Interactions
- Click handoff entry → expand full handoff record details
- Filter by agent / task / verdict
- Search within handoff summaries

### Data source
- `GET /api/workflows/handoffs?workflow_id={id}` → all handoffs for a workflow
- Each handoff record is a persisted markdown document

---

## View 3: Review Round Tracker

### Purpose
Per-task view showing the review iteration history — how many rounds, what failed, what was fixed.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Task: "rate limiter" — Review History                          │
│  Status: in review (round 2)    Agent: agent-B reviewing        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Round 1                                                        │
│  ├─ implement  agent-A  ✓  14:32                               │
│  ├─ review     agent-B  ✗  15:10                               │
│  │   findings: "window calculation off-by-one in edge case"     │
│  │   required: "fix boundary check in sliding_window()"         │
│  └─ fix        agent-A  ✓  15:45                               │
│                                                                 │
│  Round 2                                                        │
│  ├─ review     agent-B  ⟳  in progress                        │
│  │                                                              │
│                                                                 │
│  ┌─ History Intelligence ─────────────────────────────────┐     │
│  │ Similar past tasks averaged 1.5 review rounds          │     │
│  │ Common failure pattern: boundary/edge case handling     │     │
│  │ Source: 3 similar workflows found via btwin_search      │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key elements
- **Round number** — clear iteration count
- **Phase timeline** — implement → review → fix within each round
- **Verdict and findings** — what failed and why
- **History intelligence panel** — past similar task patterns (B-TWIN unique feature)

### Data source
- `GET /api/workflows/runs?task_id={id}` → all runs for a task
- `GET /api/workflows/handoffs?task_id={id}` → handoffs for the task
- `GET /api/workflows/similar?task_id={id}` → similar past workflows

---

## View 4: Audit Trail

### Purpose
Searchable, filterable log of all workflow transitions — who did what, when, and why.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Audit Trail                              [search: _________ ]  │
│  Filter: [all ▾] [all agents ▾] [all workflows ▾]              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  16:03  workflow_transition  task-1 review_pass → task-2 queued │
│         actor: dispatcher    workflow: api-refactoring           │
│                                                                 │
│  16:02  review_verdict       task-1 run-3 PASS                  │
│         actor: agent-B       findings: 0                        │
│                                                                 │
│  15:45  run_completed        task-1 run-3 (fix) success         │
│         actor: agent-A       handoff: ho_01JD...                │
│                                                                 │
│  15:10  review_verdict       task-1 run-2 FAIL                  │
│         actor: agent-B       findings: 1                        │
│                                                                 │
│  14:32  run_completed        task-1 run-1 (implement) success   │
│         actor: agent-A       handoff: ho_01JC...                │
│                                                                 │
│  14:30  workflow_created     api-refactoring                    │
│         actor: planner       tasks: 7                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key elements
- **Timestamp** — precise event time
- **Event type** — workflow_created, run_started, run_completed, review_verdict, workflow_transition, escalated, recovered
- **Context** — task, run, agent, handoff reference
- **Searchable** — full-text search across audit entries

### Data source
- Audit log (JSONL) read via `GET /api/workflows/audit?workflow_id={id}`
- Each entry links to the underlying document (handoff, run, review)

---

## View 5: Workflow Health

### Purpose
Operational overview showing blocked, escalated, and stale items across all workflows.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Workflow Health                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⚠ NEEDS ATTENTION (2)                                         │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ task-7 "deploy script"  HUMAN REVIEW REQUIRED        │       │
│  │ reason: 3 review failures exceeded threshold         │       │
│  │ workflow: api-refactoring  last activity: 2h ago     │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │ task-4 "logging"  STALE RUN                          │       │
│  │ reason: in_progress for 90 min with no handoff       │       │
│  │ workflow: api-refactoring  agent: agent-B            │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
│  ⏳ BLOCKED (1)                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ task-6 "error handling"  DEPENDENCY BLOCKED          │       │
│  │ waiting on: task-5 (in implement phase)              │       │
│  │ workflow: api-refactoring                            │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
│  ✓ HEALTHY (4 active workflows, 12 tasks running normally)      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Categories
- **Needs attention** — human_review_required, stale runs (watchdog-detected)
- **Blocked** — dependency-blocked tasks
- **Healthy** — normal active workflows (collapsed by default)

### Data source
- Aggregation of workflow/task/run status from API
- Watchdog sweep results

---

## View 6: History Intelligence (B-TWIN Unique)

### Purpose
Surface patterns from past workflow data that no other tool provides. This view answers: "what can we learn from our history?"

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  History Intelligence                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Review Efficiency                                              │
│  avg review rounds: 1.8 (last 30 days)                          │
│  first-pass approval rate: 45%                                  │
│  most common failure category: edge case handling (38%)         │
│                                                                 │
│  ───────────────────────────────────────────────────────────     │
│                                                                 │
│  Frequent Fix Patterns                                          │
│  1. boundary/edge case handling     12 occurrences              │
│  2. missing test coverage            8 occurrences              │
│  3. error handling gaps              5 occurrences              │
│                                                                 │
│  ───────────────────────────────────────────────────────────     │
│                                                                 │
│  Similar to Current Work                                        │
│  Current: "add rate limiter middleware"                          │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ "add auth middleware" (2026-02-28)                   │       │
│  │ 2 review rounds, fixed: token expiry edge case      │       │
│  │ lesson: "middleware needs timeout + error tests"     │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │ "add caching middleware" (2026-03-01)                │       │
│  │ 1 review round, passed first time                   │       │
│  │ lesson: "cache invalidation tested early"            │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key elements
- **Aggregate metrics** — review efficiency, approval rates, failure categories
- **Frequent patterns** — recurring review failure reasons
- **Similar work lookup** — past workflows semantically similar to current tasks

### Data source
- `btwin_search` over indexed workflow/handoff/review records
- Aggregation over audit trail entries
- This view is entirely powered by B-TWIN's existing search + indexer infrastructure

---

## Tech Stack Recommendation

### Frontend
Given B-TWIN's Python backend (FastAPI), the dashboard should use:

| Option | Pros | Cons |
|--------|------|------|
| **HTMX + Jinja2 templates** | No build step, server-rendered, minimal JS, fast to ship | Limited interactivity for complex views |
| **React SPA (Vite)** | Rich interactivity, component reuse | Adds JS build pipeline, separate dev server |
| **Hybrid: HTMX + Alpine.js** | Server-rendered with selective interactivity | Slightly more complex than pure HTMX |

### Recommendation

**HTMX + Jinja2 for MVP**, with Alpine.js for interactive elements (collapsible sections, filters, search).

Rationale:
- B-TWIN is a Python project; adding a full JS build pipeline increases maintenance burden
- Most views are read-heavy with server-rendered data — HTMX handles this well
- Pipeline view and timeline can be rendered server-side with CSS
- If interactivity needs grow beyond HTMX's capability, migrate specific views to a lightweight JS framework later

### Styling

Tailwind CSS (via CDN for MVP) with a design language inspired by:
- **Linear** — clean task/status cards
- **Grafana** — operational health views
- **GitHub Actions** — pipeline/workflow visualization

---

## Implementation Priority

| Priority | View | Reason |
|----------|------|--------|
| **1** | Pipeline View | Core operational visibility — "where is everything?" |
| **2** | Workflow Health | Actionable — "what needs my attention?" |
| **3** | Handoff Timeline | Collaboration visibility — "what happened?" |
| **4** | Audit Trail | Accountability — "who did what when?" |
| **5** | Review Round Tracker | Detail view — drill-down from pipeline cards |
| **6** | History Intelligence | Differentiator — but needs accumulated data to be useful |

Views 1–2 should ship with the orchestration engine MVP.
Views 3–5 should ship in the hardening phase.
View 6 ships after enough workflow history accumulates.

---

## Relationship to Existing Dashboard Plans

This spec refines and extends:

| Existing document | Relationship |
|-------------------|-------------|
| `2026-03-07-dashboard-ui-and-framework-extension-todo.md` Track A | This spec provides concrete view definitions for A4 (workflow dashboard UI) and expands the scope with handoff/audit/history views |
| `2026-03-03-dashboard-ui-design.md` | This spec inherits the general dashboard structure and adds workflow-specific views |
| `dashboard-product-spec.md` | This spec does not replace the product spec; it adds the workflow visualization layer |

### What this spec does NOT cover

- **Entries dashboard** (A2) — covered by existing dashboard plans
- **Sources dashboard** (A3) — covered by existing dashboard plans
- **Graph visualization** (A5) — separate concern, covered by existing plans
- **Visual polish** (A6) — deferred until views are functional
