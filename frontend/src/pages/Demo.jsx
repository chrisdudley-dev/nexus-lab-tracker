import { useCallback, useEffect, useState } from 'react'
import SamplesPanel from '../SamplesPanel.jsx'
import KanbanApp from '../components/kanban/KanbanApp.jsx'

const HEALTH_PHASE = {
  empty: 'empty',
  loading: 'loading',
  healthy: 'healthy',
  unhealthy: 'unhealthy',
  error: 'error',
}

function readHealthLabel(phase) {
  switch (phase) {
    case HEALTH_PHASE.loading:
      return 'Loading health check'
    case HEALTH_PHASE.healthy:
      return 'API reachable and healthy'
    case HEALTH_PHASE.unhealthy:
      return 'API reachable but unhealthy'
    case HEALTH_PHASE.error:
      return 'Health request failed'
    default:
      return 'No health data yet'
  }
}

function formatHealthValue(value) {
  if (value === null || value === undefined || value === '') {
    return 'Not provided'
  }

  if (typeof value === 'object') {
    return JSON.stringify(value)
  }

  return String(value)
}

function readDetailFromResponse(body, status) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return `HTTP ${status}`
  }

  if (typeof body.detail === 'string' && body.detail.trim()) {
    return `HTTP ${status}: ${body.detail}`
  }

  if (typeof body.error === 'string' && body.error.trim()) {
    return `HTTP ${status}: ${body.error}`
  }

  return `HTTP ${status}`
}

function isHealthPayload(body) {
  return Boolean(body && typeof body === 'object' && !Array.isArray(body) && body.schema === 'nexus_api_health')
}

function hasDocumentedHealthShape(body) {
  return isHealthPayload(body) && typeof body.schema_version === 'number' && typeof body.ok === 'boolean'
}

function getHealthStateClasses(phase) {
  switch (phase) {
    case HEALTH_PHASE.healthy:
      return 'healthStatusCard healthStatusCardHealthy'
    case HEALTH_PHASE.unhealthy:
      return 'healthStatusCard healthStatusCardUnhealthy'
    case HEALTH_PHASE.error:
      return 'healthStatusCard healthStatusCardError'
    case HEALTH_PHASE.loading:
      return 'healthStatusCard healthStatusCardLoading'
    default:
      return 'healthStatusCard healthStatusCardEmpty'
  }
}

export default function Demo() {
  const [tab, setTab] = useState('samples')
  const [healthState, setHealthState] = useState({
    phase: HEALTH_PHASE.empty,
    data: null,
    error: null,
  })

  const loadHealth = useCallback(async () => {
    setHealthState({
      phase: HEALTH_PHASE.loading,
      data: null,
      error: null,
    })

    try {
      const r = await fetch('/api/health', { headers: { Accept: 'application/json' } })
      const rawBody = await r.text()
      const body = rawBody.trim() ? JSON.parse(rawBody) : null

      if (!r.ok) {
        throw new Error(readDetailFromResponse(body, r.status))
      }

      if (!body || !Object.keys(body).length) {
        setHealthState({
          phase: HEALTH_PHASE.empty,
          data: null,
          error: null,
        })
        return
      }

      if (!hasDocumentedHealthShape(body)) {
        throw new Error('Unexpected response shape from /api/health')
      }

      setHealthState({
        phase: body.ok ? HEALTH_PHASE.healthy : HEALTH_PHASE.unhealthy,
        data: body,
        error: null,
      })
    } catch (e) {
      setHealthState({
        phase: HEALTH_PHASE.error,
        data: null,
        error: String(e?.message || e),
      })
    }
  }, [])

  useEffect(() => { void loadHealth() }, [loadHealth])

  const { phase, data, error } = healthState
  const statusLabel = readHealthLabel(phase)
  const isBusy = phase === HEALTH_PHASE.loading
  const showPayload = phase === HEALTH_PHASE.healthy || phase === HEALTH_PHASE.unhealthy
  const refreshLabel = isBusy ? 'Refreshing...' : phase === HEALTH_PHASE.empty ? 'Load Health' : 'Refresh Health'
  const schemaVersion = data?.schema_version
  const healthDetails = [
    ['Schema', data?.schema],
    ['Schema version', schemaVersion === undefined || schemaVersion === null ? null : schemaVersion],
    ['ok', data?.ok === undefined ? null : String(data.ok)],
    ['Git revision', data?.git_rev],
    ['Database path', data?.db_path],
  ].filter(([, value]) => value !== null && value !== undefined)

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

        <span className={`healthStatusPill healthStatusPill${phase[0].toUpperCase()}${phase.slice(1)}`}>
          {statusLabel}
        </span>
      </div>

      {tab === 'samples' ? (
        <SamplesPanel />
      ) : tab === 'kanban' ? (
        <KanbanApp />
      ) : (
        <div>
          <div className="healthToolbar">
            <button onClick={loadHealth} disabled={isBusy} style={{ padding: '8px 12px', borderRadius: 10 }}>
              {refreshLabel}
            </button>
            <span className="muted">The demo reads the documented `/api/health` response shape.</span>
          </div>

          <section className={getHealthStateClasses(phase)} aria-live="polite" aria-busy={isBusy}>
            <div className="healthStatusHeader">
              <div>
                <div className="healthStatusTitle">{statusLabel}</div>
                <div className="healthStatusCopy">
                  {phase === HEALTH_PHASE.loading ? 'Fetching /api/health now.' : null}
                  {phase === HEALTH_PHASE.healthy ? 'The backend returned the documented health payload with ok=true.' : null}
                  {phase === HEALTH_PHASE.unhealthy ? 'The backend returned the documented health payload with ok=false.' : null}
                  {phase === HEALTH_PHASE.error ? error : null}
                  {phase === HEALTH_PHASE.empty ? 'No health payload has been loaded yet. Use Refresh Health to query the endpoint.' : null}
                </div>
              </div>
              <div className={`healthStatusPill healthStatusPill${phase[0].toUpperCase()}${phase.slice(1)}`}>
                {statusLabel}
              </div>
            </div>

            {phase === HEALTH_PHASE.empty ? (
              <div className="healthEmptyState">
                <div className="healthEmptyTitle">No data loaded</div>
                <p className="healthEmptyCopy">
                  The demo has not yet received a health payload. Refresh the endpoint to check whether the API is
                  reachable and whether `ok` is true.
                </p>
              </div>
            ) : null}

            {phase === HEALTH_PHASE.loading ? (
              <div className="healthEmptyState">
                <div className="healthEmptyTitle">Loading</div>
                <p className="healthEmptyCopy">Waiting for `/api/health` to respond.</p>
              </div>
            ) : null}

            {phase === HEALTH_PHASE.error ? (
              <div className="healthEmptyState">
                <div className="healthEmptyTitle">Request error</div>
                <p className="healthEmptyCopy">{error}</p>
              </div>
            ) : null}

            {showPayload ? (
              <div className="healthDetailsGrid">
                {healthDetails.map(([label, value]) => (
                  <div className="healthDetail" key={label}>
                    <div className="healthDetailLabel">{label}</div>
                    <div className="healthDetailValue">{formatHealthValue(value)}</div>
                  </div>
                ))}
              </div>
            ) : null}

            {showPayload ? (
              <pre className="healthPayload">{JSON.stringify(data, null, 2)}</pre>
            ) : null}
          </section>
        </div>
      )}
    </div>
  )
}
