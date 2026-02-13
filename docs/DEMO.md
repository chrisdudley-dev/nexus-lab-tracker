# Nexus Lab Tracker — Demo

This demo proves the project is running, reachable on LAN, and enforcing basic guardrails.

## Prereqs
- FastAPI is running behind systemd: `nexus-fastapi.service`
- nginx reverse-proxy is active on port 80
- API is reachable on LAN at: `http://<jerboa-lan-ip>/`

## Quick demo flow (2–5 minutes)

### 1) Health
- Open: `http://<jerboa-lan-ip>/health`
- Expect: `ok=true`, plus `git_rev` and `db_path`.

### 2) Auth guardrail on sample list
- Open: `http://<jerboa-lan-ip>/sample/list`
- Expect: `401 Unauthorized` when auth is required.

### 3) Metrics visibility rule
- From *Jerboa only*: `curl -fsS http://127.0.0.1/metrics | head`
- From another LAN device: `http://<jerboa-lan-ip>/metrics` should be forbidden (403).

## One-command smoke test
Run:
- `./scripts/demo_smoke.sh`

If it passes, the demo is in a known-good state.
