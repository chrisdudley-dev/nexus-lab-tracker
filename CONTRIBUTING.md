# Contributing

Thanks for contributing to Nexus Lab Tracker.

This project favors **determinism**, **operator safety**, and **reproducible snapshots**. Small, well-scoped PRs with clear regressions are the fastest way to get changes merged.

## Quick start

1) Fork and clone the repo.
2) Create a feature branch.
3) Run the core regression gate before you push:

```bash
./scripts/regress_core.sh
```

## Development setup (local)

**Prereqs**
- Python 3 (recommended: 3.10+)
- Bash (Linux/macOS; on Windows use WSL2)

Typical local flow:

```bash
# Initialize local DB + run migrations
./scripts/lims.sh init
./scripts/migrate.sh up

# Run the regression gate
./scripts/regress_core.sh
```

## Standards

- Keep CLI behavior deterministic and operator-safe.
  - Input/usage errors should return `rc=2` with actionable messages.
  - Prefer stable, machine-readable JSON outputs for automation.
- Prefer small PRs with a clear scope and tests/regressions for behavior changes.
- If you add endpoints to the local API, keep the error schema stable:
  - `{"schema":"nexus_api_error","schema_version":1,"ok":false,...}`

## Suggested workflow

- Branch name: `feat/...`, `fix/...`, `chore/...`
- Open a PR early if you want feedback.
- Ensure checks are green (CI + regressions).
- Prefer **squash merge** to keep `main` readable.
- Delete the branch after merge.

## Tests and regressions

- Minimum bar for behavior changes: add or update a regression.
- Run the core regression suite locally before pushing:

```bash
./scripts/regress_core.sh
```

If your change affects snapshots, run at least:

```bash
./scripts/lims.sh snapshot export
./scripts/lims.sh snapshot verify "$(./scripts/lims.sh snapshot latest)"
```

## Commit quality

- Keep commit messages clear and scoped.
- Avoid committing secrets or credentials. Use `.env.example` for non-sensitive configuration examples.

## Security

If you believe you’ve found a security vulnerability, please follow `SECURITY.md` and report it privately.

## License

By contributing, you agree your contributions are licensed under **AGPL-3.0-or-later** (the project’s license).
