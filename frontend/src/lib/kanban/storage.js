const KEY = 'nexus_kanban_board_v1'

function isObject(x) {
  return x !== null && typeof x === 'object' && !Array.isArray(x)
}

export function validateBoard(parsed) {
  // Minimal shape validation (tolerant of extra fields)
  if (!isObject(parsed)) return false
  if (!Array.isArray(parsed.columnOrder)) return false
  if (!isObject(parsed.columns)) return false
  if (!isObject(parsed.cards)) return false
  return true
}

export function loadBoard() {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)

    // Minimal shape validation (be tolerant to extra fields)
    if (!isObject(parsed)) return null
    if (!Array.isArray(parsed.columnOrder)) return null
    if (!isObject(parsed.columns)) return null
    if (!isObject(parsed.cards)) return null

    return parsed
  } catch {
    return null
  }
}

export function saveBoard(state) {
  try {
    if (!state) return
    // Persist only the core board model; omit transient UI selections
    const toPersist = {
      columnOrder: state.columnOrder ?? [],
      columns: state.columns ?? {},
      cards: state.cards ?? {},
    }
    localStorage.setItem(KEY, JSON.stringify(toPersist))
  } catch {
    // Ignore (e.g., quota exceeded)
  }
}

export function clearBoard() {
  try { localStorage.removeItem(KEY) } catch {}
}


export async function loadBoardRemote() {
  try {
    const r = await fetch('/api/kanban/board', { headers: { Accept: 'application/json' } })
    if (!r.ok) return null
    const j = await r.json()
    return validateBoard(j) ? j : null
  } catch {
    return null
  }
}

export async function saveBoardRemote(state) {
  const payload = {
    columnOrder: state.columnOrder ?? [],
    columns: state.columns ?? {},
    cards: state.cards ?? {},
  }
  const r = await fetch('/api/kanban/board', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(`save failed: HTTP ${r.status} ${t.slice(0, 160)}`)
  }
  return r.json().catch(() => null)
}
