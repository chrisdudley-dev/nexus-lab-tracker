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
  }

  const [samples, setSamples] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  const [selectedId, setSelectedId] = useState(null)
  const [selectedShow, setSelectedShow] = useState(null)
  const [selectedEvents, setSelectedEvents] = useState(null)


  const [sessionId, setSessionId] = useState(localStorage.getItem('nexus_session') || '')
  const [displayName, setDisplayName] = useState(localStorage.getItem('nexus_display_name') || 'Jerboa Guest')

  const authHeaders = useMemo(() => {
    const sid = (sessionId || '').trim()
    return sid ? { 'X-Nexus-Session': sid } : {}
  }, [sessionId])

  async function loadSamples(limit = 25) {
    setLoading(true); setErr(null)
    try {
      const j = await fetchJson(`/api/sample/list?limit=${encodeURIComponent(limit)}`, { headers: authHeaders })
      setSamples(j)
    } catch (e) {
      setErr(String(e?.message || e))
      setSamples(null)
    } finally {
      setLoading(false)
    }
  }

  async function guestSignIn() {
    setLoading(true); setErr(null)
    try {
      const j = await fetchJson('/api/auth/guest', {
        method: 'POST',
        body: { display_name: (displayName || 'Jerboa Guest').slice(0, 80) },
      })
      const sid = j?.session?.id || ''
      if (!sid) throw new Error('Guest sign-in returned no session id')
      setSessionId(sid)
      localStorage.setItem('nexus_session', sid)
      localStorage.setItem('nexus_display_name', displayName || 'Jerboa Guest')
    } catch (e) {
      setErr(String(e?.message || e))
    } finally {
      setLoading(false)
    }
  }

  function saveSession() {
    localStorage.setItem('nexus_session', (sessionId || '').trim())
  }
  function clearSession() {
    setSessionId('')
    localStorage.removeItem('nexus_session')
  }

  async function loadDetails(identifier) {
    const id = String(identifier || '').trim()
    if (!id) return
    setSelectedId(id)
    setLoading(true); setErr(null)
    try {
      const show = await fetchJson(`/api/sample/show?identifier=${encodeURIComponent(id)}`, { headers: authHeaders })
      const ev = await fetchJson(`/api/sample/events?identifier=${encodeURIComponent(id)}&limit=50`, { headers: authHeaders })
      setSelectedShow(show)
      setSelectedEvents(ev)
    } catch (e) {
      setErr(String(e?.message || e))
      setSelectedShow(null)
      setSelectedEvents(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadSamples(25) }, [])

  const rows = samples?.samples || []

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
        <button onClick={() => loadSamples(25)} disabled={loading} style={{ padding: '8px 12px' }}>
          Refresh Samples
        </button>
        <span style={{ opacity: 0.8 }}>
          Showing {rows.length} / {samples?.count ?? '—'}
        </span>

        <span style={{ marginLeft: 10, opacity: 0.8 }}>Session:</span>
        <input
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
          placeholder="optional X-Nexus-Session"
          style={{ padding: '8px 10px', width: 320, maxWidth: '100%' }}
        />
        <button onClick={saveSession} style={{ padding: '8px 12px' }}>Save</button>
        <button onClick={clearSession} style={{ padding: '8px 12px' }}>Clear</button>

        <span style={{ marginLeft: 10, opacity: 0.8 }}>Guest name:</span>
        <input
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          style={{ padding: '8px 10px', width: 180, maxWidth: '100%' }}
        />
        <button onClick={guestSignIn} disabled={loading} style={{ padding: '8px 12px' }}>
          Guest Sign-In
        </button>

        {loading ? <span style={{ opacity: 0.8 }}>Loading…</span> : null}
        {err ? <span style={{ color: 'crimson' }}>Error: {err}</span> : null}
      </div>

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              {['id', 'external_id', 'status', 'container', 'location', 'created_at'].map((h) => (
                <th key={h} style={{ textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid #333', fontWeight: 600 }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id} onClick={() => loadDetails(s.external_id)} style={{ cursor: 'pointer' }}>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid #222' }}>{s.id}</td>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid #222' }}>{s.external_id}</td>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid #222' }}>{s.status}</td>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid #222' }}>{s.container?.barcode || s.container_id}</td>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid #222' }}>{s.container?.location || '—'}</td>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid #222' }}>{s.created_at}</td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: '10px', opacity: 0.8 }}>No samples returned.</td></tr>
            ) : null}
          </tbody>
        </table>
        </div>
        <div style={{ width: 420, maxWidth: '42vw' }}>
          <div style={{ opacity: 0.8, marginBottom: 8 }}>
            Details {selectedId ? <span>(selected: <code>{selectedId}</code>)</span> : null}
          </div>
          <pre style={{
            background: '#111', color: '#eee', padding: 12, borderRadius: 10,
            overflowX: 'auto', lineHeight: 1.35, whiteSpace: 'pre-wrap'
          }}>
{selectedShow ? JSON.stringify({ show: selectedShow, events: selectedEvents }, null, 2) : 'Click a sample row to load /sample/show + /sample/events…'}
          </pre>
        </div>
      </div>
    </div>
  )
}


// M4: API client wrapper (Issue #94)
