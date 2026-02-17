# Canonical run path (dev + prod-style)

This is the single source of truth for how to run Nexus Lab Tracker.
If other docs conflict with this page, this page wins.

## Dev run (fast iteration)

Backend (FastAPI):
```bash
PORT=8789 scripts/run_fastapi.sh
curl -fsS http://127.0.0.1:8789/health | head -c 200; echo
```

Frontend (Vite):
```bash
cd frontend
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

Open: `http://<jerboa-ip>:5173/`

## Prod-style run (nginx + systemd + built UI)

Backend under systemd:
```bash
systemctl status nexus-fastapi --no-pager
curl -fsS http://127.0.0.1:8789/health | head -c 200; echo
```

Deploy UI build to nginx:
```bash
./scripts/web_deploy_nginx.sh
```

Verify through nginx front door:
```bash
curl -fsS http://127.0.0.1:8788/api/health | head -c 200; echo
./scripts/smoke_kanban_persistence.sh http://127.0.0.1:8788
```

## References
- `docs/systemd_nginx_wiring.md`
- `scripts/run_fastapi.sh`
- `scripts/web_deploy_nginx.sh`
- `scripts/smoke_kanban_persistence.sh`
