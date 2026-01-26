# Developer Workflow

## After cloning
Run:
- `./scripts/setup_git_hooks.sh`

This enables a pre-push gate that runs `./scripts/regress_core.sh` when pushing to `main`.

## Emergency bypass
If you must bypass the gate:
- `NEXUS_SKIP_PREPUSH=1 git push`
