# Roadmap

This roadmap is intentionally lightweight and will evolve as contributors join. The guiding values are **determinism**, **operator safety**, and **reproducible snapshots**.

_Last updated: 2026-02-02_

## Now (hardening)

Focus: make the CLI + snapshot workflows boringly reliable and easy to adopt.

- Expand regression coverage for CLI and local API contracts
- Tighten machine-readable JSON output contracts (`schema`, `schema_version`) for automation reliability
- Improve docs:
  - quickstart (first run + core concepts)
  - operator-safety rules (exit codes, invariants, failure modes)
  - API contract notes (error envelope, versioning)
- CI hygiene:
  - keep `./scripts/regress_core.sh` as the baseline gate
  - maintain secret-scanning discipline (no credentials in repo)
  - keep Actions dependencies up to date

## Next (multi-platform boundary)

Focus: stabilize the HTTP API boundary so multiple tools can integrate safely.

- Stabilize the HTTP API schema and versioning approach
- Add additional **read-only** endpoints that mirror safe CLI operations
- Define auth/identity direction for multi-device environments (without over-building early)
  - goal: minimal, composable security model
  - avoid: heavy RBAC/tenant systems until the product surface demands it

## Later (clients and deployment)

Focus: make it usable beyond a single developer laptop.

- Reference clients (web/desktop/mobile) that talk to the HTTP API boundary
- Deployment guidance for single-node and small-team setups
- Explore data-store evolution paths (SQLite → Postgres) if/when needed
  - document migration strategy and operational trade-offs before switching

## Non-goals (for now)

- Building a hosted multi-tenant SaaS
- Complex permission models or enterprise IAM integration
- Premature microservices decomposition

## How to contribute

- If you want to propose a significant change, open an issue first with scope and acceptance criteria.
- For behavior changes, include/extend regressions and run `./scripts/regress_core.sh` before pushing.
