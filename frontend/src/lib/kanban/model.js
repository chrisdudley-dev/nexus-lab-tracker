export const DEFAULT_COLUMNS = [
  { id: 'todo', title: 'To Do' },
  { id: 'doing', title: 'In Progress' },
  { id: 'done', title: 'Done' },
]

export function createInitialState() {
  const columns = {}
  for (const c of DEFAULT_COLUMNS) {
    columns[c.id] = { id: c.id, title: c.title, cardIds: [] }
  }
  const seedCards = {
    c1: { id: 'c1', title: 'Example card', subtitle: 'Drag me between columns' },
  }
  columns.todo.cardIds = ['c1']
  return {
    columnOrder: DEFAULT_COLUMNS.map((c) => c.id),
    columns,
    cards: seedCards,
    selectedCardId: null,
  }
}

export function findCardLocation(state, cardId) {
  for (const colId of state.columnOrder) {
    const idx = state.columns[colId].cardIds.indexOf(cardId)
    if (idx !== -1) return { colId, index: idx }
  }
  return null
}

function removeId(arr, id) {
  const i = arr.indexOf(id)
  if (i === -1) return arr
  const next = arr.slice()
  next.splice(i, 1)
  return next
}

function insertAt(arr, id, index) {
  const next = arr.slice()
  const i = Math.max(0, Math.min(index, next.length))
  next.splice(i, 0, id)
  return next
}

export function reducer(state, action) {
  switch (action.type) {
    case 'reset':
      return createInitialState()

    case 'select':
      return { ...state, selectedCardId: action.cardId ?? null }

    case 'add': {
      const id = action.card?.id ?? `c_${Date.now()}`
      const card = {
        id,
        title: action.card?.title ?? 'New card',
        subtitle: action.card?.subtitle ?? '',
      }
      const colId = action.colId ?? 'todo'
      return {
        ...state,
        cards: { ...state.cards, [id]: card },
        columns: {
          ...state.columns,
          [colId]: { ...state.columns[colId], cardIds: [id, ...state.columns[colId].cardIds] },
        },
        selectedCardId: id,
      }
    }

    case 'update': {
      const id = action.cardId
      if (!id || !state.cards[id]) return state
      return { ...state, cards: { ...state.cards, [id]: { ...state.cards[id], ...action.patch } } }
    }

    case 'delete': {
      const id = action.cardId
      if (!id || !state.cards[id]) return state
      const loc = findCardLocation(state, id)
      const nextColumns = { ...state.columns }
      if (loc) {
        const col = state.columns[loc.colId]
        nextColumns[loc.colId] = { ...col, cardIds: removeId(col.cardIds, id) }
      }
      const nextCards = { ...state.cards }
      delete nextCards[id]
      return {
        ...state,
        columns: nextColumns,
        cards: nextCards,
        selectedCardId: state.selectedCardId === id ? null : state.selectedCardId,
      }
    }

    case 'move': {
      const { cardId, fromColId, toColId, toIndex } = action
      if (!cardId || !fromColId || !toColId) return state
      if (!state.cards[cardId]) return state

      const fromCol = state.columns[fromColId]
      const toCol = state.columns[toColId]
      if (!fromCol || !toCol) return state

      const fromIds = removeId(fromCol.cardIds, cardId)
      const baseToIds = fromColId === toColId ? fromIds : toCol.cardIds.slice()
      const nextToIds = insertAt(baseToIds, cardId, Number.isFinite(toIndex) ? toIndex : baseToIds.length)

      return {
        ...state,
        columns: {
          ...state.columns,
          [fromColId]: { ...fromCol, cardIds: fromIds },
          [toColId]: { ...toCol, cardIds: nextToIds },
        },
      }
    }

    default:
      return state
  }
}
