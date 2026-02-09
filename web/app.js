// Nexus Lab Tracker — Demo UI scaffold
// Goal: stable place to add workflows over time (containers, samples, snapshots, etc.)
// MVP upgrades: safer fetch (timeouts + consistent errors), better UI feedback,
//              Kanban correctness (unknown statuses), persist last snapshot artifact.

const out = document.getElementById("out");
const hint = document.getElementById("hint");
const btnVerify = document.getElementById("btnSnapshotVerify");
const downloadLatest = document.getElementById("downloadLatest");

const pretty = (x) => { try { return JSON.stringify(x, null, 2); } catch { return String(x); } };

function setOutput(title, resp) {
  const status = (resp && typeof resp.status !== "undefined") ? resp.status : "??";
  const okFlag = (resp && typeof resp.ok === "boolean") ? resp.ok : undefined;
  const meta = (resp && (resp.method || resp.path)) ? `${resp.method || ""} ${resp.path || ""}`.trim() : "";
  const okLine = (okFlag === true) ? "OK" : (okFlag === false ? "ERROR" : "");
  out.textContent = [
    title,
    "",
    `${okLine}${okLine ? " — " : ""}HTTP ${status}${meta ? ` — ${meta}` : ""}`,
    pretty(resp && Object.prototype.hasOwnProperty.call(resp, "data") ? resp.data : resp)
  ].join("\n");
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(text);
}

function val(id) {
  const el = document.getElementById(id);
  return (el && el.value != null) ? String(el.value) : "";
}

function clampInt(raw, defVal, minVal, maxVal) {
  const s = String(raw ?? "").trim();
  if (s === "") return defVal;
  const n = Math.floor(Number(s));
  if (!Number.isFinite(n)) return defVal;
  return Math.max(minVal, Math.min(maxVal, n));
}

function setDisabled(ids, disabled) {
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) el.disabled = !!disabled;
  }
}

/* ----------------------------
   Safer API helpers (timeout + consistent JSON/text parsing)
---------------------------- */

async function apiFetch(path, { method = "GET", body = null, timeoutMs = 12000 } = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);

  try {
    const opts = { method, signal: ctl.signal, headers: {} };
    if (body !== null) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body || {});
    }

    const r = await fetch(path, opts);
    const ct = (r.headers.get("content-type") || "").toLowerCase();

    // Parse once, safely.
    let data;
    if (ct.includes("application/json")) data = await r.json().catch(() => null);
    else data = await r.text().catch(() => "");

    const resp = { ok: r.ok, status: r.status, data, path, method };

    // Throw for non-2xx so callers reliably end up in catch blocks.
    if (!r.ok) throw resp;
    return resp;
  } catch (e) {
    // Normalize timeouts and unknown errors into {ok:false,status,...}
    if (e && e.name === "AbortError") {
      throw { ok: false, status: 0, data: { error: "Request timed out", timeoutMs, path, method }, path, method };
    }
    if (e && typeof e === "object" && "status" in e && "data" in e) throw e;
    throw { ok: false, status: 0, data: { error: String(e), path, method }, path, method };
  } finally {
    clearTimeout(t);
  }
}

const apiGet = (path) => apiFetch(path);
const apiPost = (path, body) => apiFetch(path, { method: "POST", body });

/* ----------------------------
   Snapshot Export + Verify (persist last artifact)
---------------------------- */

const ART_KEY = "nlt:lastArtifact";
let lastArtifact = null;

function applyArtifactUI(artifact) {
  const ok = (typeof artifact === "string" && artifact.length > 0);
  if (btnVerify) btnVerify.disabled = !ok;

  if (ok) {
    setText("hint", "Ready to verify artifact: " + artifact);
    if (downloadLatest) downloadLatest.style.display = "inline";
  } else {
    setText("hint", "Verify enables after export returns an artifact path.");
    if (downloadLatest) downloadLatest.style.display = "none";
  }
}

(function restoreArtifactFromStorage() {
  try {
    const saved = localStorage.getItem(ART_KEY);
    if (saved && typeof saved === "string") {
      lastArtifact = saved;
      applyArtifactUI(lastArtifact);
    }
  } catch {
    // ignore storage failures
  }
})();

document.getElementById("btnSnapshotExport")?.addEventListener("click", async () => {
  const raw = val("includeSamples").trim();
  const include_samples = raw ? raw.split(",").map(s => s.trim()).filter(Boolean) : [];

  setDisabled(["btnSnapshotExport", "btnSnapshotVerify"], true);

  try {
    const resp = await apiPost("/snapshot/export", { exports_dir: "IGNORED_BY_SERVER", include_samples });
    setOutput("POST /snapshot/export", resp);

    const d = resp.data || {};
    lastArtifact = d.tarball || d.artifact || null;

    try {
      if (typeof lastArtifact === "string" && lastArtifact.length > 0) {
        localStorage.setItem(ART_KEY, lastArtifact);
      } else {
        localStorage.removeItem(ART_KEY);
      }
    } catch {
      // ignore storage failures
    }

    applyArtifactUI(lastArtifact);
  } catch (e) {
    setOutput("POST /snapshot/export (failed)", e);
    applyArtifactUI(null);
  } finally {
    setDisabled(["btnSnapshotExport"], false);
    if (btnVerify) btnVerify.disabled = !(typeof lastArtifact === "string" && lastArtifact.length > 0);
  }
});

btnVerify?.addEventListener("click", async () => {
  if (!lastArtifact) {
    out.textContent = "ERROR: run export first";
    return;
  }
  setDisabled(["btnSnapshotVerify", "btnSnapshotExport"], true);
  try {
    const resp = await apiPost("/snapshot/verify", { artifact: lastArtifact });
    setOutput("POST /snapshot/verify", resp);
  } catch (e) {
    setOutput("POST /snapshot/verify (failed)", e);
  } finally {
    setDisabled(["btnSnapshotVerify", "btnSnapshotExport"], false);
  }
});

/* ----------------------------
   API Health
---------------------------- */
document.getElementById("btnHealth")?.addEventListener("click", async () => {
  setDisabled(["btnHealth"], true);
  try {
    setOutput("GET /health", await apiGet("/health"));
  } catch (e) {
    setOutput("GET /health (failed)", e);
  } finally {
    setDisabled(["btnHealth"], false);
  }
});

/* ----------------------------
   Containers
---------------------------- */
document.getElementById("btnContainerAdd")?.addEventListener("click", async () => {
  const barcode = val("cBarcode").trim();
  const kind = val("cKind").trim();
  const location = val("cLocation").trim();

  if (!barcode) { out.textContent = "ERROR: barcode is required"; return; }
  if (!kind) { out.textContent = "ERROR: kind is required"; return; }

  setDisabled(["btnContainerAdd"], true);
  try {
    const r = await apiPost("/container/add", { barcode, kind, location });
    setOutput("POST /container/add", r);

    // Convenience: if you are about to add a sample, prefill its container field.
    const sc = document.getElementById("sContainer");
    if (sc) sc.value = barcode;

  } catch (e) {
    setOutput("POST /container/add (failed)", e);
  } finally {
    setDisabled(["btnContainerAdd"], false);
  }
});

document.getElementById("btnContainerList")?.addEventListener("click", async () => {
  const limit = clampInt(val("cLimit"), 25, 0, 500);
  setDisabled(["btnContainerList"], true);
  try {
    setOutput("GET /container/list", await apiGet(`/container/list?limit=${encodeURIComponent(limit)}`));
  } catch (e) {
    setOutput("GET /container/list (failed)", e);
  } finally {
    setDisabled(["btnContainerList"], false);
  }
});

/* ----------------------------
   Sample add
---------------------------- */
document.getElementById("btnSampleAdd")?.addEventListener("click", async () => {
  const specimen_type = val("sSpecimenType").trim();
  const external_id_raw = val("sExternalId").trim();
  const status = (document.getElementById("sStatus")?.value || "received").trim();
  const notes_raw = val("sNotes").trim();
  const container_raw = val("sContainer").trim();

  if (!specimen_type) { out.textContent = "ERROR: specimen_type is required"; return; }

  const body = { specimen_type, status };
  if (external_id_raw) body.external_id = external_id_raw;
  if (notes_raw) body.notes = notes_raw;
  if (container_raw) body.container = container_raw;

  setDisabled(["btnSampleAdd"], true);
  try {
    const r = await apiPost("/sample/add", body);
    setOutput("POST /sample/add", r);

    // Convenience: set Sample Report identifier to the newly created sample.
    const sm = r?.data?.sample;
    const newId = sm?.external_id || sm?.id;
    const sampleIdEl = document.getElementById("sampleId");
    if (sampleIdEl && newId) sampleIdEl.value = String(newId);

    // Refresh the Kanban board so the new card appears.
    try { await renderBoard(); } catch { /* ignore */ }
  } catch (e) {
    setOutput("POST /sample/add (failed)", e);
  } finally {
    setDisabled(["btnSampleAdd"], false);
  }
});


/* ----------------------------
   Sample report
---------------------------- */
document.getElementById("btnSampleReport")?.addEventListener("click", async () => {
  const identifier = val("sampleId").trim();
  const limitRaw = val("sampleLimit").trim();

  if (!identifier) { out.textContent = "ERROR: identifier is required"; return; }

  const body = { identifier };
  if (limitRaw !== "") body.limit = clampInt(limitRaw, 50, 0, 500);

  setDisabled(["btnSampleReport"], true);
  try {
    setOutput("POST /sample/report", await apiPost("/sample/report", body));
  } catch (e) {
    setOutput("POST /sample/report (failed)", e);
  } finally {
    setDisabled(["btnSampleReport"], false);
  }
});

/* ----------------------------
   Kanban Board (MVP)
   - Fix: unknown statuses should not vanish
   - Feedback: disable controls while moving
---------------------------- */

const STATUSES = ["received", "processing", "analyzing", "completed"];

function pickSamples(payload) {
  if (!payload) return [];
  // tolerate schema changes: samples/rows/items
  return payload.samples || payload.rows || payload.items || [];
}

function normStatus(st) {
  const s = String(st || "received").trim().toLowerCase();
  return STATUSES.includes(s) ? s : "received";
}

function el(tag, attrs = {}, children = []) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, String(v));
  }
  for (const c of children) n.appendChild(c);
  return n;
}

async function renderBoard() {
  const board = document.getElementById("board");
  const btn = document.getElementById("btnBoardRefresh");
  const limitEl = document.getElementById("boardLimit");

  if (!board || !btn) return;

  const limit = clampInt(limitEl?.value, 200, 0, 500);

  btn.disabled = true;
  board.innerHTML = `<div class="muted">Loading…</div>`;

  try {
    const resp = await apiGet(`/sample/list?limit=${encodeURIComponent(limit)}`);
    const data = resp.data || {};
    const samples = pickSamples(data);

    // group by status (normalized)
    const by = {};
    for (const st of STATUSES) by[st] = [];
    for (const sm of samples) {
      const st = normStatus(sm && sm.status);
      by[st].push(sm);
    }

    board.innerHTML = "";
    board.appendChild(el("div", { class: "boardGrid" }, STATUSES.map((st) => {
      const col = el("div", { class: "boardCol" }, [
        el("div", { class: "boardColTitle", text: st }),
      ]);

      const list = el("div", { class: "boardColList" }, []);

      for (const sm of (by[st] || [])) {
        const ident = sm?.external_id || sm?.identifier || sm?.id;
        const title = sm?.external_id || sm?.id || "(sample)";
        const container = (sm?.container && (sm.container.barcode || sm.container.id))
          ? (sm.container.barcode || sm.container.id)
          : (sm?.container_id ?? "");
        const subtitle = container ? `container: ${container}` : "";

        const sel = el("select", { class: "moveSelect" }, STATUSES.map((opt) =>
          el("option", { value: opt, text: opt, ...(opt === st ? { "selected": "selected" } : {}) }, [])
        ));

        const card = el("div", { class: "boardCard" }, [
          el("div", { class: "boardCardTitle", text: String(title) }),
          el("div", { class: "boardCardSub", text: String(subtitle) }),
          el("div", { class: "boardCardActions" }, [
            el("span", { class: "muted", text: "Move to:" }),
            sel
          ])
        ]);

        sel.addEventListener("change", async () => {
          const to = sel.value;

          if (!ident) {
            out.textContent = "ERROR: sample identifier missing; cannot move";
            sel.value = st;
            return;
          }

          // prevent double actions
          sel.disabled = true;
          btn.disabled = true;

          try {
            const r = await apiPost("/sample/status", {
              identifier: String(ident),
              status: String(to),
              note: "kanban move"
            });

            // If API returns ok false, show payload for the demo
            if (r?.data && typeof r.data === "object" && "ok" in r.data && !r.data.ok) {
              setOutput("POST /sample/status (kanban)", r);
            } else {
              out.textContent = `Moved ${String(title)} → ${String(to)}`;
            }
          } catch (e) {
            setOutput("POST /sample/status (kanban failed)", e);
          } finally {
            try { await renderBoard(); } catch { /* ignore */ }
          }
        });

        list.appendChild(card);
      }

      col.appendChild(list);
      return col;
    })));
  } catch (e) {
    setOutput("GET /sample/list (board failed)", e);
    board.innerHTML = `<div class="muted">Board failed to load. Check Output for details.</div>`;
  } finally {
    btn.disabled = false;
  }
}

// Wire button
document.getElementById("btnBoardRefresh")?.addEventListener("click", renderBoard);
// Auto-load once
setTimeout(() => { try { renderBoard(); } catch {} }, 250);
