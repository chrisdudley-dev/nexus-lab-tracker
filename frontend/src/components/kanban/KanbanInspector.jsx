import { findCardLocation } from '../../lib/kanban/model.js'

export default function KanbanInspector({ state, dispatch }) {
  const id = state.selectedCardId
  const card = id ? state.cards[id] : null
  const loc = id ? findCardLocation(state, id) : null
  const colId = loc?.colId

  if (!card) {
    return (
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 12, opacity: 0.8 }}>
        Select a card to inspect/edit.
      </div>
    )
  }

  const prevCol = colId === 'done' ? 'doing' : colId === 'doing' ? 'todo' : null
  const nextCol = colId === 'todo' ? 'doing' : colId === 'doing' ? 'done' : null

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 12 }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>Selected</div>
      <div style={{ opacity: 0.8, fontSize: 13, marginBottom: 10 }}>Column: {colId ?? 'unknown'}</div>

      <label style={{ display: 'block', fontSize: 13, opacity: 0.8 }}>Title</label>
      <input
        value={card.title}
        onChange={(e) => dispatch({ type: 'update', cardId: id, patch: { title: e.target.value } })}
        style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb', marginBottom: 10 }}
      />

      <label style={{ display: 'block', fontSize: 13, opacity: 0.8 }}>Subtitle</label>
      <input
        value={card.subtitle ?? ''}
        onChange={(e) => dispatch({ type: 'update', cardId: id, patch: { subtitle: e.target.value } })}
        style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb', marginBottom: 12 }}
      />

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button
          onClick={() => dispatch({ type: 'delete', cardId: id })}
          style={{ padding: '8px 12px', borderRadius: 10, border: '1px solid #e5e7eb', cursor: 'pointer' }}
        >
          Delete
        </button>
        <button
          onClick={() => dispatch({ type: 'add', colId: 'todo', card: { title: 'New card', subtitle: '' } })}
          style={{ padding: '8px 12px', borderRadius: 10, border: '1px solid #e5e7eb', cursor: 'pointer' }}
        >
          Add card
        </button>
        {prevCol ? (
          <button
            onClick={() => dispatch({ type: 'move', cardId: id, toColId: prevCol })}
            style={{ padding: '8px 12px', borderRadius: 10, border: '1px solid #e5e7eb', cursor: 'pointer' }}
          >
            Move left
          </button>
        ) : null}
        {nextCol ? (
          <button
            onClick={() => dispatch({ type: 'move', cardId: id, toColId: nextCol })}
            style={{ padding: '8px 12px', borderRadius: 10, border: '1px solid #e5e7eb', cursor: 'pointer' }}
          >
            Move right
          </button>
        ) : null}
      </div>
    </div>
  )
}
