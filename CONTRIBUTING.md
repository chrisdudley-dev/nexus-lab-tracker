# Contributing

Thanks for contributing to Nexus Lab Tracker.

## Quick start
1) Fork and clone the repo.
2) Run the core regression suite before pushing:
   ./scripts/regress_core.sh

## Standards
- Keep CLI behavior deterministic and operator-safe.
  - Input/usage errors should return rc=2 with actionable messages.
- Prefer small PRs with a clear scope and tests/regressions for behavior changes.
- If you add endpoints to the local API, keep the error schema stable:
  - {"schema":"nexus_api_error","schema_version":1,"ok":false,...}

## License
By contributing, you agree your contributions are licensed under AGPL-3.0-or-later (the project’s license).
