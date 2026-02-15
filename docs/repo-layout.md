# Repository layout (canonical)

## Canonical homes
- Frontend (React/Vite): `frontend/`
- API (FastAPI entrypoint): `api/main.py` (run as `uvicorn api.main:app`)
- Domain/DB logic: `src/nexus_lab_tracker/` and `lims/` (legacy modules; migrating)
- Ops/deploy notes/config: `ops/`
- Legacy quarantine: `legacy/`

## Compatibility
Older docs/scripts may refer to `web-react/`. The React app has moved to `frontend/`.
Use:
- `./scripts/cd-web-react.sh` (compat helper)
