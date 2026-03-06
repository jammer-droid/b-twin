---
doc_version: 1
last_updated: 2026-03-06
status: proposed
---

# Common Foundation for Workflow + Dashboard Design

**Date:** 2026-03-06
**Status:** Approved design basis

## Goal
Build the common foundation that both of these future features will share:
1. workflow orchestration (epic/task/task-run based execution)
2. record visualization / dashboard UX

The purpose of this foundation is to prevent duplicated storage, duplicated API conventions, and incompatible UI state models.

## Why a common foundation first
Both features need the same lower-level capabilities:
- stable document metadata and frontmatter conventions
- storage and indexing compatibility
- shared API conventions
- shared UI shell and navigation
- shared audit and recovery behavior

If implemented separately first, they will likely diverge and force rework.

## Design Principles
- Reuse existing B-TWIN mechanisms wherever possible.
- Prefer markdown + frontmatter as the first persisted state layer.
- Treat indexer/audit/checksum/doc_version as core infrastructure, not feature-specific details.
- Keep the MVP deterministic and inspectable.
- Let the framework own queue/state progression; let agents execute assigned work units only.

## Scope of the common foundation MVP

### 1. Shared data model conventions
Define a shared document contract across workflow docs and dashboard-visible docs.

Minimum shared metadata fields:
- `doc_version`
- `status`
- `updated_at`
- `record_type`
- `title` (where applicable)
- `created_at`

Workflow-specific documents will additionally include identifiers such as:
- `workflow_id`
- `epic_id`
- `task_id`
- `run_id`
- `phase`
- `retry_count`
- `assigned_agent`

This gives the system a uniform way to store, inspect, version, and render documents in both automation and UI contexts.

### 2. Storage / indexer compatibility layer
The existing storage/indexer system should be extended so workflow documents become first-class indexable records.

The foundation must verify:
- workflow docs can be enumerated by storage
- workflow docs receive stable `doc_id` / `record_type`
- metadata required for filtering/search is preserved
- checksum + `doc_version` behavior works for workflow docs as it does for existing entries

This layer is not the workflow engine itself; it is the compatibility substrate that makes workflow state visible, searchable, and recoverable.

### 3. Shared API base structure
Before building feature-specific endpoints, define an API structure that can host both sets cleanly.

Target structure:
- `/api/workflows/*` for orchestration objects and transitions
- `/api/entries/*` for dashboard record browsing/searching
- `/api/sources/*` for source registry management
- shared response envelope and error format
- shared auth/admin gating conventions where needed

The foundation phase should organize FastAPI modules/routes so later feature work plugs into a clean structure rather than extending one oversized collab file indefinitely.

### 4. Shared UI shell
The web UI should gain a minimal navigation shell that future pages can share.

Minimum shell scope:
- base layout
- navigation links for workflows / entries / sources / summary / ops
- placeholder page structure or route affordance
- consistent loading/error/empty-state pattern

This is not a full dashboard implementation yet. It is the shared frame that prevents later UI fragmentation.

### 5. Shared state / audit / recovery rules
The foundation must define how state transitions are recorded and recovered.

Principles:
- all meaningful workflow state changes should be auditable
- interrupted work must be resumable from stored state
- recovery should depend on persisted state, not hidden agent memory
- queue progression decisions should be reconstructable from task records + task-run records + audit trail

This aligns directly with existing B-TWIN ideas such as:
- `mark_pending`
- `refresh`
- `reconcile`
- `repair`
- `doc_version`
- checksum validation

## What is intentionally NOT in this foundation phase
To keep the foundation small and reusable, this phase does **not** try to fully ship:
- the complete workflow engine UX
- the complete records dashboard UX
- advanced visualization (graph/kanban/timelines)
- asynchronous worker orchestration infrastructure
- cross-agent scheduling heuristics

Those sit on top of this layer.

## Relationship to existing B-TWIN architecture
This design assumes the current B-TWIN core remains the base system:
- markdown/frontmatter storage remains primary persisted truth in MVP
- indexer remains responsible for discoverability and sync integrity
- audit remains append-only execution evidence
- ops dashboard continues to expose system health signals

The common foundation extends these, rather than replacing them.

## Expected outputs of the foundation phase
A successful foundation phase should leave the repo with:
- a stable workflow document schema
- storage support for workflow docs
- indexer compatibility verified for workflow docs
- API structure ready for workflow + dashboard endpoints
- minimal shared UI shell
- explicit audit/recovery rules documented in code/docs

## Success criteria
The foundation phase is complete when:
1. workflow docs can be created/read/indexed/versioned reliably
2. shared metadata conventions are documented and enforced in tests
3. API modules can cleanly host both workflow and dashboard surfaces
4. a shared web shell exists for future pages
5. persisted state is sufficient to recover or continue execution without relying on hidden agent context

## Recommended next step
Create a detailed implementation plan that executes this common foundation in small, testable tasks before separately expanding:
- workflow orchestration feature set
- dashboard/visualization feature set
