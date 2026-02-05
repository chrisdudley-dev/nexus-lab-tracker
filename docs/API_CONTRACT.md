# Nexus Lab Tracker — API Contract (v1)

This document is the single source of truth for what the HTTP API promises to client apps
(web, Android, desktop). Keep it stable, versioned, and backwards-compatible.

## Contract rules

1) Every JSON response includes:
- schema (string)
- schema_version (integer)
- ok (boolean)

2) Backwards compatibility:
- Additive changes are allowed (new fields, new endpoints).
- Breaking changes require a new schema_version (or a new endpoint).

3) No client-controlled filesystem paths:
- Any client-provided output directory is ignored for safety.
- IDs are validated; traversal/unsafe strings are rejected.

## Common error shape

All errors return:

{
  "schema": "nexus_api_error",
  "schema_version": 1,
  "ok": false,
  "error": "bad_request",
  "detail": "human-readable detail"
}

Common error values:
- bad_request (400)
- not_found (404)
- internal_error (500)
- command_failed (400)
- command_timeout (504)

---

## GET /health

Response (200):

{
  "schema": "nexus_api_health",
  "schema_version": 1,
  "ok": true,
  "db_path": "/path/to/db",
  "git_rev": "abcdef0"
}

---

## POST /snapshot/export

Request:

{
  "exports_dir": "IGNORED_BY_SERVER",
  "include_samples": ["S-001"]
}

Notes:
- exports_dir is accepted for forward compatibility but is ignored for safety.
- include_samples must be allowlisted sample IDs.

Response (200): schema nexus_snapshot_export_result (v1)

---

## POST /snapshot/verify

Request:
{ "artifact": "/path/to/snapshot.tar.gz" }

Response (200): schema nexus_snapshot_verify_result (v1)

---

## POST /sample/report

Request:
{ "identifier": "S-001", "limit": 50 }

Response (200): schema nexus_sample_report (v1)

---

## GET /exports/latest

Downloads the most recent API-created snapshot tarball.
Response (200): Content-Type application/gzip

---

## Planned workflow endpoints (next)

### POST /container/add
Request:
{ "barcode": "TUBE-1", "kind": "tube", "location": "bench-A" }

Response (200): schema nexus_container (v1)

### GET /container/list?limit=25
Response (200): schema nexus_container_list (v1)
