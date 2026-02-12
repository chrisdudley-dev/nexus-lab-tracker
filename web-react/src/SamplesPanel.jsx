import { useEffect, useMemo, useState } from 'react'

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
  const [samples, setSamples] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

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

      <div style={{ overflowX: 'auto' }}>
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
              <tr key={s.id}>
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
    </div>
  )
}
