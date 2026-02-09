# Sprint: 2026-02-09 — Milestone A Demo Gates

## Sprint Goal
Make the MVP demo path repeatable and evidence-based (no “hand-waving”), aligned to the quality gates in context-for-rag.

## Success Criteria (Definition of Done for this sprint)
- A newcomer can follow docs to run the demo end-to-end without tribal knowledge.
- A single command/script produces a “green” proof bundle (or clearly fails with actionable output).
- Web UI expectations are documented (and optionally testable headless).

## Tasks
### A) Demo flow documentation (must)
- [ ] Write `docs/DEMO.md` with:
  - setup
  - start API
  - open UI
  - create container + sample
  - move sample status + note
  - show audit/provenance signal (if visible)
  - verify `/metrics`
- [ ] Link DEMO doc from README (or docs index)

### B) Proof script (must)
- [ ] Add `scripts/demo_smoke.sh` that:
  - runs `./scripts/regress_core.sh`
  - prints a short “demo checklist” at end
  - (optional) captures output to `report/demo_proof/` with timestamp

### C) Web UI headless check (should)
- [ ] Document how to run the existing headless check:
  - `JERBOA_WEBUI_HEADLESS=1 ./scripts/regress_core.sh`
  - list dependencies + troubleshooting notes
- [ ] Decide: keep headless optional on Pi, but runnable on a dev machine/CI later

### D) Quality gates mapping (should)
- [ ] Create `docs/QUALITY_GATES.md` with a table:
  - Gate (from QDRC)
  - Evidence command
  - Where output is captured
  - Pass/Fail meaning

## Evidence commands
- Core proof:
  - `./scripts/regress_core.sh`
- Optional web UI proof:
  - `JERBOA_WEBUI_HEADLESS=1 ./scripts/regress_core.sh`
