# Roadmap

This roadmap is intentionally lightweight and may evolve as contributors join.

Near-term (hardening)
- Expand regression coverage for CLI and local API contracts
- Tighten JSON output contracts for automation reliability
- Improve docs: quickstart, operator-safety rules, and API contract notes

Mid-term (multi-platform boundary)
- Stabilize the HTTP API schema and versioning approach
- Add additional read-only endpoints that mirror safe CLI operations
- Define auth/identity direction for multi-device environments (without over-building early)

Long-term (clients and deployment)
- Reference clients (web/desktop/mobile) that talk to the HTTP API boundary
- Deployment guidance for single-node and small-team setups
- Explore data-store evolution paths (SQLite -> Postgres) if/when needed
