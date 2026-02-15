#!/usr/bin/env python3
"""
Source-based regression for demo UI status flows in legacy/web/index.html.

We validate invariants introduced by the UI patches:
  - AUTOFILL_STATUS_FROM_SHOW exists inside doShow(), and doShow assigns sample.status into the status control.
  - STATUS_POST_AUTOREFRESH_V1 exists inside doStatus(), and doStatus calls doShow() AFTER /sample/status.

Exit codes:
  0 = OK
  2 = FAIL
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(2)


HTML_PATH = Path("legacy/web/index.html")
s = HTML_PATH.read_text("utf-8", errors="replace")

MARK1 = "AUTOFILL_STATUS_FROM_SHOW"
MARK2 = "STATUS_POST_AUTOREFRESH_V1"

if MARK1 not in s:
    fail(f"missing marker: {MARK1}")
if MARK2 not in s:
    fail(f"missing marker: {MARK2}")


def extract_function_body(src: str, name: str) -> str:
    """
    Extract body of (async )function <name>() { ... } with basic JS string/comment handling.
    Returns body (inside braces), or fails.
    """
    m = re.search(
        rf"(?m)^(?P<ind>\s*)(?:async\s+)?function\s+{re.escape(name)}\s*\(\s*\)\s*\{{",
        src,
    )
    if not m:
        fail(f"could not find `function {name}()` in legacy/web/index.html")

    start_brace = m.end() - 1  # points at '{'
    i = start_brace + 1
    depth = 1

    in_s = in_d = in_t = False
    in_lc = in_bc = False
    esc = False

    while i < len(src) and depth > 0:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < len(src) else ""

        if in_lc:
            if ch == "\n":
                in_lc = False
            i += 1
            continue

        if in_bc:
            if ch == "*" and nxt == "/":
                in_bc = False
                i += 2
                continue
            i += 1
            continue

        if in_s:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == "'":
                in_s = False
            i += 1
            continue

        if in_d:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_d = False
            i += 1
            continue

        if in_t:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == "`":
                in_t = False
            i += 1
            continue

        # enter comment
        if ch == "/" and nxt == "/":
            in_lc = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_bc = True
            i += 2
            continue

        # enter strings
        if ch == "'":
            in_s = True
            i += 1
            continue
        if ch == '"':
            in_d = True
            i += 1
            continue
        if ch == "`":
            in_t = True
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1

        i += 1

    if depth != 0:
        fail(f"could not match braces for {name}()")

    body_start = start_brace + 1
    body_end = i - 1
    return src[body_start:body_end]


doShow = extract_function_body(s, "doShow")
doStatus = extract_function_body(s, "doStatus")

# --- doShow assertions ---
if MARK1 not in doShow:
    fail(f"{MARK1} not found inside doShow()")
if "/sample/show" not in doShow:
    fail("doShow() does not reference /sample/show")

after = doShow.split(MARK1, 1)[1]
if not re.search(r"\.value\s*=", after):
    fail("doShow() does not assign to a `.value` after AUTOFILL marker")
if not re.search(r"\bstatus\b", after):
    fail("doShow() does not reference `status` after AUTOFILL marker")

# --- doStatus assertions ---
if MARK2 not in doStatus:
    fail(f"{MARK2} not found inside doStatus()")
if "/sample/status" not in doStatus:
    fail("doStatus() does not reference /sample/status")

after2 = doStatus.split(MARK2, 1)[1]
if not re.search(r"\bdoShow\s*\(", after2):
    fail("doStatus() does not call doShow() after STATUS_POST marker")

print("OK: web UI status regression passed (source-based contract)")
raise SystemExit(0)
