import { useEffect, useState } from 'react'
import SamplesPanel from '../SamplesPanel.jsx'

export default function Demo() {
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
    <div>
      <h2 style={{ marginTop: 0 }}>Demo</h2>

      <div className="row" style={{ marginBottom: 14 }}>
        <button onClick={() => setTab('samples')} disabled={tab === 'samples'} className="btn">
          Samples
        </button>
        <button onClick={() => setTab('health')} disabled={tab === 'health'} className="btn">
          Health
        </button>

        {loading ? <span className="muted">Loading…</span> : null}
        {err ? <span className="error">Error: {err}</span> : null}
        {health?.ok ? <span className="ok">API OK</span> : null}
      </div>

      {tab === 'samples' ? (
        <SamplesPanel />
      ) : (
        <div>
          <div className="row" style={{ marginBottom: 12 }}>
            <button onClick={loadHealth} disabled={loading} className="btn">
              Refresh Health
            </button>
          </div>
          <pre className="pre">{health ? JSON.stringify(health, null, 2) : 'No data'}</pre>
        </div>
      )}
    </div>
  )
}
