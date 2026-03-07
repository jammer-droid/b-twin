---
doc_version: 1
last_updated: 2026-03-07
status: proposed
---

# Dashboard UI + Framework Extension TODO

## Purpose
This document captures the remaining work that was intentionally left out of the common foundation phase.

It exists so we can distinguish between:
- **done foundation work** (shared storage / route scaffold / shell / recovery contract)
- **remaining product work** (real dashboard UI, workflow framework expansion, richer UX/state flow)

## Current State Summary
The repo now has the **common foundation** for workflow + dashboard work:
- shared metadata model
- shared-record storage/indexability
- route scaffold under `/api/workflows/*`, `/api/entries/*`, `/api/sources/*`
- minimal shared UI shell/navigation
- recovery contract and verification docs

What it does **not** have yet:
- complete dashboard UI
- complete workflow orchestration framework
- production-grade workflow views and queue operations
- advanced graph/visualization UX
- full end-to-end framework behavior on top of the shared foundation

---

## Track A — Dashboard UI TODO

### A1. App shell → real dashboard app
**Goal:** Replace placeholder/shell behavior with a navigable product UI.

**Remaining work:**
- build real page layouts for:
  - Home
  - Entries
  - Sessions (if retained in IA)
  - Summary
  - Sources
  - Workflows
  - Graph
- unify loading / empty / error states
- make selected/active nav state obvious
- ensure page routes and API calls are aligned

**Definition of done:**
- a user can move through all primary dashboard sections without hitting placeholder-only views
- each section renders real data or explicit empty-state UX

---

### A2. Entries dashboard
**Goal:** Turn record browsing into a usable dashboard surface.

**Remaining work:**
- searchable entry list UI
- filter controls (date / tags / topic / project / source as applicable)
- detail side panel or detail view
- metadata badges and frontmatter-derived summaries
- pagination or windowing strategy if entry count grows
- empty state when no entries match filters

**Definition of done:**
- user can browse, filter, inspect, and understand stored entries from the dashboard

---

### A3. Sources dashboard
**Goal:** Make source registry/scan behavior visible and operable from UI.

**Remaining work:**
- source list view
- source enabled/disabled status surface
- scan/refresh triggers with feedback
- last scan/result status display
- error and retry UX

**Definition of done:**
- a user can inspect and operate source scanning without leaving the dashboard

---

### A4. Workflow dashboard UI
**Goal:** Show workflow state, queue progression, and operator actions.

**Remaining work:**
- epic list and detail view
- ordered task list per epic
- task run history / current phase display
- verdict / retry / blocker status visualization
- next actionable work item display
- human-review-required badge/surface
- workflow recovery visibility (what is resumable / what is blocked)

**Definition of done:**
- a user can inspect workflow execution state and understand what should happen next

---

### A5. Graph / visualization page
**Goal:** Ship the promised dashboard visualization layer beyond a placeholder route.

**Remaining work:**
- implement graph page using actual record relationships
- decide initial graph source of truth:
  - explicit `related` links only, or
  - metadata overlap heuristics, or
  - hybrid approach
- node styling / cluster coloring / hover behavior
- zoom, pan, filters
- performance guardrails for larger datasets
- clear fallback if graph data is sparse

**Definition of done:**
- graph page is interactive and useful, not just decorative

---

### A6. Dashboard visual polish
**Goal:** Apply the approved Observatory design language consistently.

**Remaining work:**
- color token consistency
- card/list/badge/search component polish
- hover/focus/selection states
- dark-theme consistency
- motion/transitions where worth the complexity
- responsive behavior for narrow widths

**Definition of done:**
- dashboard feels cohesive rather than scaffolded

---

## Track B — Framework Extension TODO

### B1. Workflow domain models
**Goal:** Implement first-class workflow records on top of the foundation.

**Remaining work:**
- `EpicRecord`
- `TaskRecord`
- `TaskRunRecord`
- validation for identifiers, status, phase, verdict, retry counters
- deterministic storage/read/list helpers

**Definition of done:**
- workflow state is stored as first-class persisted records, not ad hoc docs

---

### B2. Workflow transition engine
**Goal:** Make workflow progression deterministic in code.

**Remaining work:**
- implement transition rules for:
  - implement → review
  - review fail → fix
  - fix → review
  - review pass → done
- unlock next task when predecessor completes
- escalation threshold for repeated failures
- pure logic module with tests

**Definition of done:**
- task progression can be reasoned about and tested without API/UI coupling

---

### B3. Workflow API
**Goal:** Expand scaffold routes into real workflow operations.

**Remaining work:**
- create/list epics
- create/list tasks
- create/list task runs
- complete run
- submit review verdict
- surface blocker / escalation / recovery states
- response envelope/error consistency with existing API patterns

**Definition of done:**
- workflow objects can be created and advanced through API calls alone

---

### B4. Auto-progression + recovery hooks
**Goal:** Support persisted implement→review→fix loops and restart safety.

**Remaining work:**
- dispatcher that computes next action from saved state
- automatic follow-up run creation
- recovery after interrupted execution
- resumable status surfaces
- clear human-review-required exit path

**Definition of done:**
- workflow execution can resume from persisted records without hidden runtime memory

---

### B5. Indexer/search integration for workflow records
**Goal:** Make workflow records fully searchable and visible in operational surfaces.

**Remaining work:**
- verify workflow docs are indexed with stable metadata
- define retrieval/filter semantics for workflow objects
- ensure audit/recovery fields remain queryable
- confirm index refresh/reconcile behavior after workflow updates

**Definition of done:**
- workflow records behave like first-class discoverable records operationally

---

### B6. Framework/page modularization
**Goal:** Prevent `collab_api.py` and related modules from becoming a dumping ground.

**Remaining work:**
- split API modules if route growth continues
- separate dashboard concerns from workflow concerns where sensible
- define stable ownership boundaries for:
  - storage
  - models
  - gates/dispatchers
  - API layer
  - UI layer

**Definition of done:**
- adding new workflow/dashboard features does not increase structural debt sharply

---

## Track C — Verification / Release Readiness TODO

### C1. Integration tests for real user flows
**Remaining work:**
- install → init → serve-api happy path
- project-scoped dashboard flow
- workflow create → review → fix → done flow
- interrupted/recovery flow
- source scan and dashboard reflection flow

### C2. Manual test guide for dashboard/workflows
**Remaining work:**
- explicit manual checklist for UI validation
- operator checklist for workflow recovery/escalation
- graph page smoke test steps

### C3. Docs and onboarding alignment
**Remaining work:**
- README examples for project-scoped shared records
- workflow usage docs once APIs/UI are real
- dashboard screenshots or example walkthroughs once stable

---

## Suggested Execution Order

### Option 1 — Product-visible first
1. A1 app shell → real dashboard app
2. A2 entries dashboard
3. A3 sources dashboard
4. A4 workflow dashboard UI
5. A5 graph page
6. A6 dashboard polish
7. B-track framework completion underneath as needed

**Best when:** goal is quick visible progress for end users.

### Option 2 — Framework first
1. B1 workflow domain models
2. B2 workflow transition engine
3. B3 workflow API
4. B4 auto-progression + recovery hooks
5. B5 indexer/search integration
6. A4 workflow dashboard UI
7. Remaining dashboard pages/polish

**Best when:** goal is reliable workflow behavior before richer UI.

### Recommended
**Recommendation: Option 2 with early lightweight UI checkpoints — reason: the dashboard/workflow surfaces will move faster and with less rework if the workflow state model and transitions are stable first.**

---

## Immediate Next Tasks
If we continue from here, the next concrete implementation tasks should be:

1. create `workflow_models.py` and workflow storage tests
2. implement workflow gate / transition rules
3. expand workflow API beyond health endpoints
4. add minimal real workflow dashboard page
5. then expand entries/sources/graph dashboard surfaces

---

## Not To Confuse With Foundation Done List
The following items are **already done enough for foundation scope** and should not be mistaken for full product completion:
- shared record metadata baseline
- shared-record storage/indexability
- route scaffolding
- minimal shared shell/navigation
- recovery contract documentation

These are prerequisites, not finish lines.
