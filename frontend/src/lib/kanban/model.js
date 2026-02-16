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
    c1: { id: 'c1', title: 'Example card', subtitle: 'Replace with sample-backed data' },
  }
  columns.todo.cardIds = ['c1']
  return {
    columnOrder: DEFAULT_COLUMNS.map(c => c.id),
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

export function reducer(state, action) {
  switch (action.type) {
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
        const cur = nextColumns[loc.colId]
        nextColumns[loc.colId] = { ...cur, cardIds: cur.cardIds.filter(x => x !== id) }
      }
      const nextCards = { ...state.cards }
      delete nextCards[id]
      return {
        ...state,
        cards: nextCards,
        columns: nextColumns,
        selectedCardId: state.selectedCardId === id ? null : state.selectedCardId,
      }
    }

    case 'move': {
      const { cardId, toColId } = action
      if (!cardId || !toColId) return state
      const loc = findCardLocation(state, cardId)
      if (!loc) return state
      if (loc.colId === toColId) return state
      const fromCol = state.columns[loc.colId]
      const toCol = state.columns[toColId]
      if (!fromCol || !toCol) return state
      return {
        ...state,
        columns: {
          ...state.columns,
          [loc.colId]: { ...fromCol, cardIds: fromCol.cardIds.filter(x => x !== cardId) },
          [toColId]: { ...toCol, cardIds: [cardId, ...toCol.cardIds] },
        },
      }
    }

    default:
      return state
  }
}
