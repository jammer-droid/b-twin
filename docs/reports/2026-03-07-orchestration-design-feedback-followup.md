---
doc_version: 1
last_updated: 2026-03-07
status: draft
responds_to:
  - docs/reports/2026-03-07-orchestration-design-feedback-response.md
---

# Follow-up Feedback on Orchestration Design Corrections

## Purpose
This document captures the remaining follow-up feedback after reviewing:
- `docs/reports/2026-03-07-orchestration-design-feedback-response.md`

The prior correction document significantly improved the design.
The overall architecture direction now looks sound.
This follow-up focuses only on the remaining precision gaps that should be resolved before implementation begins.

---

## Overall Assessment
The design is now in good shape strategically.
The remaining work is not a major architectural rewrite.
It is mostly about making the runtime design more implementation-safe and less ambiguous.

In other words:
- **big direction change is not needed**,
- **design precision improvements are still worthwhile**.

---

## Remaining Improvement Areas

### 1. Review result normalization should be specified more explicitly
The corrected design makes the completion handler robust against missing structured output.
That is good.
However, the review phase still needs a more explicit canonical ingestion rule.

### Why this matters
A review run is not just a generic handoff.
It is the point where the workflow engine decides whether to:
- advance,
- create a fix run,
- pause,
- escalate.

If review output is not normalized consistently, the review/fix loop becomes unstable.

### Recommended addition
Define a canonical review normalization contract such as:
- `verdict`: `pass | fail | hold`
- `findings`: structured list with stable schema
- `required_fixes`: normalized actionable fix list
- `severity` or optional priority markers if used later
- fallback rule when review output is incomplete or partially structured

### Recommended design invariant
> Review completion must always produce a canonical verdict record, even if the worker output is partial or weakly structured.

---

### 2. TaskRun lifecycle wording should be tightened
The design now correctly centers event records as the source of truth.
However, `TaskRunRecord` lifecycle wording still risks confusion.

The design currently implies both:
- append-only / immutable event behavior,
- and run status update on completion.

### Why this matters
Implementation needs to know whether a run record is:
- fully immutable from creation,
- mutable until close,
- or represented as separate started/completed events.

### Recommended clarification
Use wording like:
- a `TaskRunRecord` is created in an open state,
- limited lifecycle fields may transition while the run is active,
- once closed/completed/cancelled, it becomes immutable.

### Alternative
If stronger event purity is desired later, split into:
- `RunStartedEvent`
- `RunCompletedEvent`

But for MVP, the "open then closed then immutable" model is probably enough.

---

### 3. `awaiting_input` should have stricter boundaries
The corrected design introduces `awaiting_input`, which is useful.
But it is still broad enough that the runtime could overuse it.

### Why this matters
If the engine sends too many ambiguous cases into `awaiting_input`, continuity weakens again.
The system becomes overly conservative and stops too often.

### Recommended clarification
Define exactly when `awaiting_input` is allowed versus when the task should instead be:
- `blocked`
- `interrupted`
- `escalated`

### Suggested interpretation
- `blocked` = dependency or prerequisite not yet satisfied
- `interrupted` = execution stopped unexpectedly and is recoverable
- `awaiting_input` = external human/system clarification is required before safe progression
- `escalated` = retry/review threshold exceeded or workflow requires human judgment

### Recommended design invariant
> `awaiting_input` should only be used when the runtime cannot safely infer the next step without external clarification.

---

### 4. MVP linearity assumption should be stated explicitly
The current design implies a mostly linear progression model:
- implement
- review
- fix
- review
- done
- next task

That is fine for MVP.
But it should be made explicit.

### Why this matters
Without an explicit MVP scope statement, later readers may assume the design already supports:
- broad DAG execution,
- arbitrary parallel branches,
- merge barriers,
- complex dependency graphs.

### Recommended addition
Add a scope statement such as:

> MVP assumes predominantly ordered or linear task progression with optional review/fix loops. General DAG scheduling, arbitrary fan-out/fan-in, and advanced workflow graph semantics are out of scope for the first implementation.

This will reduce scope creep and ambiguity.

---

### 5. Continuation/context builder should get a more concrete contract
The current correction document correctly places continuation context in the execution adapter layer.
That is good.
But the input/output contract is still too implicit.

### Why this matters
The context builder will be one of the most important parts of the runtime.
If it is underspecified, continuity quality will vary and implementation will become ad hoc.

### Recommended addition
Define the context builder with:

#### Inputs
- workflow summary
- current task snapshot
- latest run snapshot
- latest review record
- unresolved fixes
- recent file changes / artifact references
- current phase
- current status
- next action intent

#### Outputs
- implementer prompt bundle
- reviewer prompt bundle
- fixer prompt bundle

### Recommended design invariant
> The continuation context builder is deterministic from persisted workflow state plus runtime-observable execution artifacts.

---

### 6. Add explicit transition examples
The corrected design defines the rules well, but examples would still help a lot.

### Why this matters
Transition examples reduce ambiguity for implementers and reviewers.
They also make idempotency and trigger-priority rules easier to verify.

### Recommended examples to add
1. implement success -> review queued
2. review fail -> fix queued
3. fix success -> review queued
4. duplicate completion event -> skipped due to existing transition key
5. interrupted run -> watchdog recovery dispatch
6. retry threshold exceeded -> task escalated, workflow escalated

### Recommended format
A small transition table or 1-2 sequence diagrams would be enough.

---

## Suggested Priority of Remaining Changes
If only a few refinements are made before implementation planning, prioritize them in this order:

1. **review result normalization rules**
2. **clear boundary between `awaiting_input`, `blocked`, `interrupted`, and `escalated`**
3. **TaskRun lifecycle clarification**
4. **explicit MVP linearity/scope statement**
5. **context builder contract**
6. **transition examples**

---

## Final Assessment
The corrected design is now strong enough that the main architecture direction does not need to change.
The remaining work is precision work.

That means:
- the design should move forward,
- but these follow-up clarifications should ideally be incorporated before implementation starts.

## Bottom line
The architecture now looks sound.
The remaining feedback is about making the design safer to implement, easier to verify, and harder to misread.
