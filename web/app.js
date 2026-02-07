// Nexus Lab Tracker — Demo UI scaffold
// Goal: stable place to add workflows over time (containers, samples, snapshots, etc.)

const out = document.getElementById("out");
const hint = document.getElementById("hint");
const btnVerify = document.getElementById("btnSnapshotVerify");
const downloadLatest = document.getElementById("downloadLatest");
let lastArtifact = null;

const pretty = (x) => { try { return JSON.stringify(x, null, 2); } catch { return String(x); } };

async function apiGet(path) {
  const r = await fetch(path);
  const ct = (r.headers.get("content-type") || "").toLowerCase();
  const data = ct.includes("application/json") ? await r.json() : await r.text();
  return { status: r.status, data };
}

async function apiPost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  const ct = (r.headers.get("content-type") || "").toLowerCase();
  const data = ct.includes("application/json") ? await r.json() : await r.text();
  return { status: r.status, data };
}

function setOutput(title, resp) {
  out.textContent = `${title}\n\nHTTP ${resp.status}\n${pretty(resp.data)}`;
}

function val(id) {
  const el = document.getElementById(id);
  return (el && el.value != null) ? String(el.value) : "";
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(text);
}

// Health
document.getElementById("btnHealth")?.addEventListener("click", async () => {
  try { setOutput("GET /health", await apiGet("/health")); }
  catch (e) { out.textContent = "ERROR: " + e; }
});

// Containers (wired after we add HTML controls)
document.getElementById("btnContainerAdd")?.addEventListener("click", async () => {
  const barcode = val("cBarcode").trim();
  const kind = val("cKind").trim();
  const location = val("cLocation").trim();
  try { setOutput("POST /container/add", await apiPost("/container/add", { barcode, kind, location })); }
  catch (e) { out.textContent = "ERROR: " + e; }
});

document.getElementById("btnContainerList")?.addEventListener("click", async () => {
  const limitRaw = val("cLimit").trim();
  const limit = limitRaw ? Math.max(0, Math.floor(Number(limitRaw))) : 25;
  try { setOutput("GET /container/list", await apiGet(`/container/list?limit=${encodeURIComponent(limit)}`)); }
  catch (e) { out.textContent = "ERROR: " + e; }
});

// Sample report
document.getElementById("btnSampleReport")?.addEventListener("click", async () => {
  const identifier = val("sampleId").trim();
  const limitRaw = val("sampleLimit").trim();
  const body = { identifier };
  if (limitRaw !== "") body.limit = Math.max(0, Math.floor(Number(limitRaw)));
  try { setOutput("POST /sample/report", await apiPost("/sample/report", body)); }
  catch (e) { out.textContent = "ERROR: " + e; }
});

// Snapshot export + verify
document.getElementById("btnSnapshotExport")?.addEventListener("click", async () => {
  const raw = val("includeSamples").trim();
  const include_samples = raw ? raw.split(",").map(s => s.trim()).filter(Boolean) : [];
  try {
    const resp = await apiPost("/snapshot/export", { exports_dir: "IGNORED_BY_SERVER", include_samples });
    setOutput("POST /snapshot/export", resp);

    const d = resp.data || {};
    lastArtifact = d.tarball || d.artifact || null;

    if (typeof lastArtifact === "string" && lastArtifact.length > 0) {
      btnVerify.disabled = false;
      setText("hint", "Ready to verify artifact: " + lastArtifact);
      if (downloadLatest) downloadLatest.style.display = "inline";
    } else {
      btnVerify.disabled = true;
      setText("hint", "Verify enables after export returns an artifact path.");
      if (downloadLatest) downloadLatest.style.display = "none";
    }
  } catch (e) {
    out.textContent = "ERROR: " + e;
  }
});

btnVerify?.addEventListener("click", async () => {
  if (!lastArtifact) { out.textContent = "ERROR: run export first"; return; }
  try { setOutput("POST /snapshot/verify", await apiPost("/snapshot/verify", { artifact: lastArtifact })); }
  catch (e) { out.textContent = "ERROR: " + e; }
});


// ----------------------------
// Kanban Board (MVP)
// ----------------------------
const STATUSES = ["received", "processing", "analyzing", "completed"];

function pickSamples(payload) {
  if (!payload) return [];
  // tolerate schema changes: samples/rows/items
  return payload.samples || payload.rows || payload.items || [];
}

function el(tag, attrs = {}, children = []) {
  const n = document.createElement(tag);
  for (const [k,v] of Object.entries(attrs)) {
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
  if (!board || !btn) return;

  const limitRaw = (document.getElementById("boardLimit")?.value || "").trim();
  const limit = limitRaw ? Math.max(0, Math.floor(Number(limitRaw))) : 200;

  btn.disabled = true;
  try {
    const resp = await apiGet(`/sample/list?limit=${encodeURIComponent(limit)}`);
    const data = resp.data || {};
    const samples = pickSamples(data);

    // group by status
    const by = {};
    for (const st of STATUSES) by[st] = [];
    for (const sm of samples) {
      const st = (sm && sm.status) ? String(sm.status) : "received";
      (by[st] || (by[st] = [])).push(sm);
    }

    board.innerHTML = "";
    board.appendChild(el("div", { class: "boardGrid" }, STATUSES.map(st => {
      const col = el("div", { class: "boardCol" }, [
        el("div", { class: "boardColTitle", text: st }),
      ]);

      const list = el("div", { class: "boardColList" }, []);
      for (const sm of (by[st] || [])) {
        const ident = sm.external_id || sm.identifier || sm.id;
        const title = sm.external_id || sm.id || "(sample)";
        const container = (sm.container && (sm.container.barcode || sm.container.id)) ? (sm.container.barcode || sm.container.id) : (sm.container_id ?? "");
        const subtitle = container ? `container: ${container}` : "";

        const sel = el("select", { class: "moveSelect" }, STATUSES.map(opt =>
          el("option", { value: opt, text: opt, ...(opt === st ? {"selected":"selected"} : {}) }, [])
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
          try {
            const r = await apiPost("/sample/status", {
              identifier: String(ident),
              status: String(to),
              message: "kanban move"
            });
            if (!(r.data && r.data.ok)) {
              setOutput("POST /sample/status (kanban)", r);
            }
          } catch (e) {
            out.textContent = "ERROR: " + e;
          } finally {
            await renderBoard();
          }
        });

        list.appendChild(card);
      }

      col.appendChild(list);
      return col;
    })));
  } catch (e) {
    out.textContent = "ERROR: " + e;
  } finally {
    btn.disabled = false;
  }
}

// Wire button
document.getElementById("btnBoardRefresh")?.addEventListener("click", renderBoard);
// Auto-load once
setTimeout(() => { try { renderBoard(); } catch {} }, 250);
