# nexus-lab-tracker

## Multi-machine configuration pattern

- Commit `.env.example` as a template.
- Each machine creates its own local `.env` (never commit it).
- Shell scripts load `.env` via `scripts/env.sh`, and compute `REPO_ROOT` dynamically.
- Prefer repo-relative paths (e.g., `./logs`, `./exports`) over absolute, machine-specific paths.
