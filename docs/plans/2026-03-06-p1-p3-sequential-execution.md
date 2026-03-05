# P1→P3 Sequential Delivery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the remaining B-TWIN roadmap from P1 through P3 in strict sequence, with measurable integrity/operations outcomes.

**Architecture:** Build in vertical slices: first observability and integrity enforcement (P1), then runtime capability expansion (P2), then release-grade operationalization (P3). Each slice must ship with tests and operational docs before moving forward.

**Tech Stack:** Python (FastAPI, Typer, Pydantic), YAML/JSONL storage, ChromaDB vector store, pytest

---

### Task 1: P1-1 Sync-gap KPI instrumentation

**Files:**
- Modify: `src/btwin/core/indexer.py`
- Modify: `src/btwin/core/indexer_manifest.py` (if needed)
- Modify: `src/btwin/core/vector.py` (if needed)
- Modify: `src/btwin/cli/main.py`
- Modify: `src/btwin/api/collab_api.py`
- Test: `tests/test_core/test_indexer.py`
- Test: `tests/test_cli/test_indexer_cli.py`
- Test: `tests/test_api/test_indexer_api.py`

**Acceptance:**
- Can report
  - write→indexed latency
  - manifest↔vector mismatch count
  - repair success rate and average repair time
- KPI output exposed via CLI/API and validated by tests.

### Task 2: P1-2 Integrity gate hardening (handoff/complete)

**Files:**
- Modify: `src/btwin/api/collab_api.py`
- Modify: `src/btwin/core/indexer.py`
- Modify: `src/btwin/core/storage.py` (if helper needed)
- Test: `tests/test_api/test_collab_api.py`
- Test: `tests/test_core/test_indexer.py` (if needed)

**Acceptance:**
- Handoff/complete requires indexed+checksum-consistent state.
- On mismatch/failure, repair policy runs as defined and is tested.

### Task 3: P1-3 Recall quality uplift

**Files:**
- Modify: `src/btwin/core/vector.py`
- Modify: `src/btwin/core/btwin.py`
- Modify: `src/btwin/core/indexer.py` (if retrieval metadata support needed)
- Test: `tests/test_core/test_vector.py`
- Test: `tests/test_core/test_btwin.py`

**Acceptance:**
- Hybrid retrieval path exists (lexical + vector)
- MMR dedupe and temporal decay supported
- Embedding cache behavior covered by tests

### Task 4: P2-1 OpenClaw attached adapter

**Files:**
- Modify/Create around runtime adapter layer under `src/btwin/core/`
- Modify: `src/btwin/api/collab_api.py`
- Modify: `src/btwin/cli/main.py`
- Test: adapter + runtime integration tests

**Acceptance:**
- OpenClaw memory/search config integration path operational
- Audit/event envelope compatible in attached mode.

### Task 5: P2-2 Standalone minimum runtime

**Files:**
- Modify runtime/config/core wiring in `src/btwin/`
- Test standalone mode behavior

**Acceptance:**
- Core works with no OpenClaw dependency in standalone mode.

### Task 6: P2-3 Ops dashboard completion

**Files:**
- Modify UI/API in `src/btwin/api/collab_api.py`
- Test API/UI endpoints

**Acceptance:**
- Dashboard exposes indexer status, failure queue, repair history, gate violations.

### Task 7: P3 operationalization

**Files:**
- Docs: `docs/indexer-operations.md`, new release/runbook docs
- Test suites and scenario scripts

**Acceptance:**
- Regression/recovery/performance checks documented and runnable.
- Release checklist and weekly KPI reporting procedure finalized.
