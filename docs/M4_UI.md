# M4 — Minimal UI (static)

This milestone provides a tiny, dependency-free UI served by nginx at:

- `/ui/` (static HTML from `web/ui/index.html`)

The UI is intentionally minimal and exists to validate end-to-end wiring:
- `GET /health`
- `POST /auth/guest`
- `GET /sample/list` (with `X-Nexus-Session`)

## Serving model
nginx serves `/ui/` as static content from the repository `web/` directory, and proxies all other paths to FastAPI.

This keeps the UI:
- simple to deploy (no Node/Vite needed),
- easy to audit,
- useful as a LAN-only “control panel” during early milestones.

## Security notes
- `/metrics` should remain local-only (loopback allow, deny all else).
- Prefer HTTPS for browser access; self-signed cert is acceptable for LAN development.

## Smoke testing
Run:
- `./scripts/ui_smoke.sh`

This validates:
- `/ui/` is reachable through nginx
- `/health` returns ok=true
- `/auth/guest` returns a session token
- `/sample/list` returns 200 when the session header is provided
