import { useEffect, useState } from 'react'
import SamplesPanel from './SamplesPanel.jsx'
import './App.css'

export default function App() {
  const [tab, setTab] = useState('samples')
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  async function loadHealth() {
    setLoading(true); setErr(null)
    try {
      const r = await fetch('/api/health', { headers: { Accept: 'application/json' } })
      const j = await r.json().catch(async () => ({ raw: await r.text() }))
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${JSON.stringify(j).slice(0, 300)}`)
      setHealth(j)
    } catch (e) {
      setErr(String(e?.message || e))
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadHealth() }, [])

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', padding: 24, fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
      <h1 style={{ marginBottom: 6 }}>Nexus Lab Tracker — Web UI (React)</h1>
      <div style={{ opacity: 0.8, marginBottom: 14 }}>
        Dev server uses <code>/api/…</code> via Vite proxy → backend <code>127.0.0.1:8787</code>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
        <button onClick={() => setTab('samples')} disabled={tab === 'samples'} style={{ padding: '8px 12px' }}>
          Samples
        </button>
        <button onClick={() => setTab('health')} disabled={tab === 'health'} style={{ padding: '8px 12px' }}>
          Health
        </button>

        {loading ? <span style={{ opacity: 0.8 }}>Loading…</span> : null}
        {err ? <span style={{ color: 'crimson' }}>Error: {err}</span> : null}
        {health?.ok ? <span style={{ color: 'green' }}>API OK</span> : null}
      </div>

      {tab === 'samples' ? (
        <SamplesPanel />
      ) : (
        <div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}>
            <button onClick={loadHealth} disabled={loading} style={{ padding: '8px 12px' }}>
              Refresh Health
            </button>
          </div>
          <pre style={{ background: '#111', color: '#eee', padding: 16, borderRadius: 10, overflowX: 'auto', lineHeight: 1.35 }}>
            {health ? JSON.stringify(health, null, 2) : 'No data'}
          </pre>
        </div>
      )}
    </div>
  )
}
