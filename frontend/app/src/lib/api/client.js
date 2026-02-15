// Minimal API client for the demo UI.
// - Base URL comes from VITE_API_BASE (or defaults to same-origin).
// - Guest session token is stored in localStorage and sent as a header.

const DEFAULT_BASE = ""; // same-origin by default

function getBaseUrl() {
  return (import.meta?.env?.VITE_API_BASE ?? DEFAULT_BASE).replace(/\/+$/, "");
}

const SESSION_KEY = "nexus_guest_session";

export function getSession() {
  return localStorage.getItem(SESSION_KEY) || "";
}

export function setSession(token) {
  if (!token) localStorage.removeItem(SESSION_KEY);
  else localStorage.setItem(SESSION_KEY, token);
}

function buildHeaders(extra) {
  const h = { "Content-Type": "application/json", ...(extra || {}) };
  const session = getSession();
  if (session) h["X-Session"] = session; // adjust if your API expects a different header
  return h;
}

async function request(path, opts = {}) {
  const base = getBaseUrl();
  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    ...opts,
    headers: buildHeaders(opts.headers),
  });

  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }

  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: (path) => request(path, { method: "GET" }),
  post: (path, body) => request(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
};
