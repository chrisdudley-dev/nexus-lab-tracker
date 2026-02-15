import { useEffect, useMemo, useState } from 'react'
import { api, setSession, getSession } from "./lib/api/client";

async function fetchJson(url, { method = 'GET', headers = {}, body = null } = {}) {
  const h = { Accept: 'application/json', ...headers }
  const init = { method, headers: h }
  if (body !== null) {
    init.headers = { 'Content-Type': 'application/json', ...init.headers }
    init.body = JSON.stringify(body)
  }
  const r = await fetch(url, init)
  const text = await r.text()
  let data = null
  try { data = JSON.parse(text) } catch { /* keep raw */ }
  if (!r.ok) {
    const msg = (data && (data.detail || data.error || data.message)) ? JSON.stringify(data) : text
    throw new Error(`HTTP ${r.status}: ${String(msg).slice(0, 300)}`)
  }
  return data ?? { raw: text }
}

export default function SamplesPanel() {

  const [authMsg, setAuthMsg] = useState("");
  const [displayName, setDisplayName] = useState("Guest");
  const [sessionId, setSessionId] = useState(getSession());

  async function doGuestAuth() {
    setAuthMsg("");
    try {
      const r = await api.post("/auth/guest", { display_name: displayName });
      const sid = r?.session?.id || r?.session || "";
      if (!sid) throw new Error("No session id returned");
      setSession(sid);
      setSessionId(sid);
      setAuthMsg("Signed in (guest).");
    } catch (e) {
      setAuthMsg(`Auth failed: ${e?.data?.message || e?.message || e}`);
    }
  }

  const [samples, setSamples] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)


  async function loadSamples() {
    setErr(null);
    setLoading(true);
    try {
      const r = await api.get("/sample/list");
      setSamples(r);
    } catch (e) {
      const msg = e?.data?.message || e?.data?.error || e?.message || String(e);
      setErr(msg);
    } finally {
      setLoading(false);
    }
  }

  const [selectedId, setSelectedId] = useState(null)
  const [selectedShow, setSelectedShow] = useState(null)
  const [selectedEvents, setSelectedEvents] = useState(null)
}


// M4: API client wrapper (Issue #94)
