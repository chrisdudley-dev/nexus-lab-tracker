# Governance

Nexus Lab Tracker is maintained under a simple **maintainer-led** model.

## Roles

- **Maintainer:** Sets overall direction and has final say on merges, releases, and project policy.
- **Contributors:** Anyone who opens issues, proposes changes, or submits pull requests.

## Decision making

- Day-to-day decisions happen in issues and pull requests.
- Well-scoped proposals with clear acceptance criteria are preferred.
- In case of disagreement, the maintainer will summarize trade-offs and decide based on project values and roadmap fit.

## Quality bar

Operator safety and deterministic behavior are core project values.

- Input/usage errors should return `rc=2` with actionable messages.
- Changes that affect behavior should include or update regressions.
- Run `./scripts/regress_core.sh` before pushing changes.

## Scope control

- Small, incremental PRs are preferred.
- Large or cross-cutting changes should be proposed as an issue first.

## Code review

PRs may be requested to adjust scope, add tests, or clarify behavior contracts (CLI and API).

## Releases

- Releases are maintainer-driven.
- Backwards-incompatible changes should be clearly called out in release notes.
- CI should be green before tagging a release.

## Conduct

All project participation is governed by `CODE_OF_CONDUCT.md`.

## Security

Please report vulnerabilities privately via the process described in `SECURITY.md`. Do not open public issues for suspected security problems.

## Becoming a maintainer

As the project grows, the maintainer may invite additional maintainers based on sustained, high-quality contributions and demonstrated alignment with the project’s values.
