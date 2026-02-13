# Quality Gates

These gates define “demo ready” and prevent regressions.

## Gate table

| Gate | What it proves | Command / Check | Pass condition |
|---|---|---|---|
| API health | process + DB reachable | `curl -fsS http://127.0.0.1/health` | JSON contains `ok:true` |
| Auth guardrail | sample list protected when required | `curl -i http://127.0.0.1/sample/list` | `401` when `NEXUS_REQUIRE_AUTH_FOR_SAMPLES=1` |
| Metrics local-only | metrics not exposed broadly | LAN: `curl -i http://<lan-ip>/metrics` | `403` |
| Reverse proxy | stable exposure via nginx | `curl -fsS http://127.0.0.1/health` (via nginx) | `200` |
| Demo smoke | fast repeatable verification | `./scripts/demo_smoke.sh` | `PASS` |

## Notes
- These gates are intentionally minimal. Expand only when they protect real demo risk.
