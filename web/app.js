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
