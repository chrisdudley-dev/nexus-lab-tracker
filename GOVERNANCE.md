# Governance

Nexus Lab Tracker is maintained under a simple "maintainer-led" model.

Decision making:
- The maintainer sets overall direction and has final say on merges and releases.
- Discussion happens in issues and pull requests. Well-scoped proposals with clear acceptance criteria are preferred.

Quality bar:
- Operator safety and deterministic behavior are core project values.
- Input/usage errors should return rc=2 with actionable messages.
- Changes that affect behavior should include or update regressions.
- Run ./scripts/regress_core.sh before pushing changes.

Scope control:
- Small, incremental PRs are preferred.
- Large or cross-cutting changes should be proposed as an issue first.

Code review:
- PRs may be requested to adjust scope, add tests, or clarify behavior contracts (CLI and API).
