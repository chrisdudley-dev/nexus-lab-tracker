import { useEffect, useState } from 'react'
import './App.css'

export default function App() {
  const [health, setHealth] = useState(null)
  const [err, setErr] = useState(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetch('/api/health', { headers: { 'Accept': 'application/json' } })
      const text = await r.text()
      let data = null
      try { data = JSON.parse(text) } catch { /* keep raw */ }
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${text.slice(0, 200)}`)
      setHealth(data ?? { raw: text })
    } catch (e) {
      setErr(String(e?.message || e))
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 24, fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
      <h1 style={{ marginBottom: 6 }}>Nexus Lab Tracker — Web UI (React)</h1>
      <div style={{ opacity: 0.8, marginBottom: 18 }}>
        Dev server calls <code>/api/health</code> (proxied by Vite) → backend <code>127.0.0.1:8787/health</code>
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16 }}>
        <button onClick={load} disabled={loading} style={{ padding: '8px 12px', cursor: loading ? 'not-allowed' : 'pointer' }}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
        {err ? <span style={{ color: 'crimson' }}>Error: {err}</span> : null}
        {health?.ok ? <span style={{ color: 'green' }}>API OK</span> : null}
      </div>

      <pre style={{
        background: '#111', color: '#eee', padding: 16, borderRadius: 10,
        overflowX: 'auto', lineHeight: 1.35
      }}>
        {health ? JSON.stringify(health, null, 2) : (loading ? 'Loading…' : 'No data')}
      </pre>
    </div>
  )
}
