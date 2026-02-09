# Nexus Lab Tracker — Demo Guide (Milestone A)

This guide is the “show it works” path for the MVP: start the API, open the UI, perform a small workflow, and verify health/metrics.

## 1) Quick proof (fastest)
Runs the full core regression suite and writes a timestamped proof log:

```bash
./scripts/demo_smoke.sh
```

Proof output:
- `report/demo_proof/<timestamp>/demo_smoke.log`

## 2) Start the API
Default (loopback + default port):

```bash
./scripts/lims_api.sh
```

Optional alternate port:

```bash
./scripts/lims_api.sh --port 8087
```

## 3) Verify endpoints
Assuming default port `8787`:

```bash
curl -fsS http://127.0.0.1:8787/health
curl -fsS http://127.0.0.1:8787/metrics | head -n 30
```

## 4) Open the UI
Open in a browser:
- `http://127.0.0.1:8787/`

## 5) MVP workflow (what to show)
1) Create/select a container
2) Add a sample (unique `external_id`)
3) Move status + add a note
4) Refresh and confirm status/note persist
5) Confirm `/metrics` responds
