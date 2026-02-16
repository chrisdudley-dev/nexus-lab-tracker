import { useEffect, useReducer, useState } from 'react'
import SamplesPanel from '../SamplesPanel.jsx'
import KanbanBoard from '../components/kanban/KanbanBoard.jsx'
import KanbanInspector from '../components/kanban/KanbanInspector.jsx'
import { createInitialState, reducer } from '../lib/kanban/model.js'

export default function Demo() {
  const [tab, setTab] = useState('samples')
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [kstate, dispatch] = useReducer(reducer, undefined, createInitialState)

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

  const columns = [
    { id: 'todo', title: 'To Do', cards: [{ id: 'c1', title: 'Example card', subtitle: 'Replace with sample-backed data' }] },
    { id: 'doing', title: 'In Progress', cards: [] },
    { id: 'done', title: 'Done', cards: [] },
  ]

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Demo</h2>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
        <button onClick={() => setTab('samples')} disabled={tab === 'samples'} style={{ padding: '8px 12px', borderRadius: 10 }}>
          Samples
        </button>
        <button onClick={() => setTab('kanban')} disabled={tab === 'kanban'} style={{ padding: '8px 12px', borderRadius: 10 }}>
          Kanban
        </button>
        <button onClick={() => setTab('health')} disabled={tab === 'health'} style={{ padding: '8px 12px', borderRadius: 10 }}>
          Health
        </button>

        {loading ? <span style={{ opacity: 0.8 }}>Loading…</span> : null}
        {err ? <span style={{ color: 'crimson' }}>Error: {err}</span> : null}
        {health?.ok ? <span style={{ color: 'green' }}>API OK</span> : null}
      </div>

      {tab === 'samples' ? (
        <SamplesPanel />
      ) : tab === 'kanban' ? (
        <div style={{ display: 'grid', gap: 12 }}>
        <KanbanBoard
          columns={kstate.columnOrder.map((colId) => ({
            id: colId,
            title: kstate.columns[colId].title,
            cards: kstate.columns[colId].cardIds.map((id) => kstate.cards[id]).filter(Boolean),
          }))}
          onCardClick={(c) => dispatch({ type: 'select', cardId: c.id })}
        />
        <KanbanInspector state={kstate} dispatch={dispatch} />
      </div>
      ) : (
        <div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}>
            <button onClick={loadHealth} disabled={loading} style={{ padding: '8px 12px', borderRadius: 10 }}>
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
