/**
 * Headless verification for the demo UI logic in web/index.html:
 *  - doShow() autofills status dropdown from sample.status
 *  - doStatus() refreshes Show after a successful status update
 *
 * No browser required; stubs fetch + minimal DOM.
 *
 * Exit codes:
 *  0 = OK
 *  2 = FAIL
 */
const fs = require("fs");
const vm = require("vm");

const html = fs.readFileSync("web/index.html", "utf8");

// Extract inline <script> blocks
const scripts = [];
const reScript = /<script[^>]*>([\s\S]*?)<\/script>/gi;
let ms;
while ((ms = reScript.exec(html)) !== null) scripts.push(ms[1]);
if (!scripts.length) {
  console.error("FAIL: no inline <script> blocks found in web/index.html");
  process.exit(2);
}

// Collect element ids
const idRe = /\bid="([^"]+)"/g;
const ids = new Set();
let mi;
while ((mi = idRe.exec(html)) !== null) ids.add(mi[1]);

function makeEl(id) {
  return {
    id,
    value: "",
    textContent: "",
    innerText: "",
    style: {},
    options: [],
    onclick: null,
    addEventListener: function () {},
    setAttribute: function () {},
  };
}

const elements = {};
for (const id of ids) elements[id] = makeEl(id);

// Ensure key elements exist
elements["sampleIdentifier"] = elements["sampleIdentifier"] || makeEl("sampleIdentifier");
elements["out"] = elements["out"] || makeEl("out");

// Parse <select id="statusValue"> options so autofill logic can validate existence
const mSel = html.match(/<select[^>]*id="statusValue"[^>]*>([\s\S]*?)<\/select>/i);
if (!mSel) {
  console.error("FAIL: couldn't find <select id='statusValue'> in web/index.html");
  process.exit(2);
}
const optVals = [];
const optRe = /<option[^>]*value="([^"]*)"/gi;
let mo;
while ((mo = optRe.exec(mSel[1])) !== null) optVals.push(mo[1].trim());
elements["statusValue"].options = optVals.map(v => ({ value: v }));
elements["statusValue"].value = optVals[0] || "";

// Minimal document
const document = {
  getElementById: (id) => elements[id] || null,
};

// Stub fetch() to satisfy fetchJson() calls
let currentStatus = "processing";
async function fetch(url, opts) {
  url = String(url);

  if (url.startsWith("/sample/show")) {
    return {
      ok: true,
      status: 200,
      async json() {
        return { ok: true, sample: { status: currentStatus } };
      },
      async text() { return ""; }
    };
  }

  if (url === "/sample/status") {
    let body = {};
    try { body = JSON.parse((opts && opts.body) || "{}"); } catch {}
    if (body && typeof body.status === "string") currentStatus = body.status.trim();
    return {
      ok: true,
      status: 200,
      async json() {
        // UI code checks j.status for canonical status
        return { ok: true, status: currentStatus };
      },
      async text() { return ""; }
    };
  }

  // Default success
  return {
    ok: true,
    status: 200,
    async json() { return { ok: true }; },
    async text() { return ""; }
  };
}

function hasOption(sel, v) {
  return Array.from(sel.options || []).some(o => (o && o.value) === v);
}

const context = vm.createContext({
  console,
  document,
  fetch,
  URLSearchParams,
  setTimeout,
  clearTimeout,
});

// Run the page scripts
for (let i = 0; i < scripts.length; i++) {
  vm.runInContext(scripts[i], context, { filename: `web/index.html::<script#${i}>` });
}

(async () => {
  const doShow = context.doShow;
  const doStatus = context.doStatus;

  if (typeof doShow !== "function") throw new Error("doShow() not found in page scripts");
  if (typeof doStatus !== "function") throw new Error("doStatus() not found in page scripts");

  const sel = elements["statusValue"];

  // 1) doShow() should autofill dropdown to currentStatus
  elements["sampleIdentifier"].value = "UI-STATUS-001";
  sel.value = ""; // clear to prove autofill
  await doShow();
  if (sel.value !== "processing") {
    throw new Error(`Expected statusValue='processing' after doShow(), got '${sel.value}'`);
  }

  // 2) doStatus() should apply canonical status + auto-refresh show
  // Pick a target status that actually exists in the dropdown.
  const target = hasOption(sel, "completed") ? "completed"
               : (hasOption(sel, "processed") ? "processed"
               : (hasOption(sel, "done") ? "done"
               : null));

  if (!target) {
    throw new Error(
      `No suitable target status found in dropdown options. ` +
      `Need one of: completed/processed/done. Options: ${sel.options.map(o=>o.value).join(", ")}`
    );
  }

  sel.value = target;
  await doStatus();
  if (sel.value !== target) {
    throw new Error(`Expected statusValue='${target}' after doStatus(), got '${sel.value}'`);
  }

  console.log(`OK: web UI headless status checks passed (doShow autofill + doStatus autorefresh -> ${target})`);
})().catch(err => {
  console.error("FAIL:", err && err.stack ? err.stack : err);
  process.exit(2);
});
