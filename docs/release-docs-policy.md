# Release Docs Policy (Open Source)

This document defines what to publish (and what to keep internal) when preparing B-TWIN for public release.

## Goal

Keep public docs focused on user value and contributor onboarding, while removing internal planning noise.

## 1) Keep Public (recommended)

- `README.md` — quick start, install, usage examples
- `docs/getting-started.md` — first-run flow
- `docs/configuration.md` — config/env/data directory behavior
- `docs/faq.md` — common issues and fixes
- `CONTRIBUTING.md` — contribution guide

## 2) Rewrite/Summarize Before Publishing

Internal decision logs can be useful, but should be curated:

- `docs/architecture-decisions.md` → keep only stable, user-relevant decisions
- Deferred ideas should be marked clearly or moved to internal tracking
- Remove speculative details that do not help users adopt the project

## 3) Keep Internal / Exclude from Public Release

- Raw internal discussion notes
- Early-stage strategy documents and prioritization rationale
- Temporary experiment logs not tied to shipped behavior

## 4) Pre-Release Documentation Checklist

- [ ] No secrets or private identifiers (paths, tokens, personal data)
- [ ] Installation steps are verified on a clean environment
- [ ] Commands in README are copy-paste runnable
- [ ] Current behavior matches documentation (no stale API/docs)
- [ ] Deferred/planned items are clearly labeled as non-shipping
- [ ] Public docs explain both MCP and non-MCP usage paths (if both are supported)

## 5) Publishing Principle

Prefer clarity over completeness:
- Public docs should answer: “How do I install, run, and trust this?”
- Internal docs should answer: “How did we decide this?”

Both are useful, but they should be separated.
