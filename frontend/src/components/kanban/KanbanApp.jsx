import { useMemo, useReducer, useState, useEffect } from 'react'
import KanbanBoard from './KanbanBoard.jsx'
import { createInitialState, reducer } from '../../lib/kanban/model.js'

function Panel({ card, onSave, onDelete, onClose }) {
  const [title, setTitle] = useState('')
  const [subtitle, setSubtitle] = useState('')

  useEffect(() => {
    setTitle(card?.title ?? '')
    setSubtitle(card?.subtitle ?? '')
  }, [card?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontWeight: 700 }}>Inspector</div>
        {card ? <button onClick={onClose} className="btn">Close</button> : null}
      </div>

      {!card ? (
        <div style={{ opacity: 0.75, fontSize: 13 }}>
          Select a card to edit it, or click "Add card".
        </div>
      ) : (
        <>
          <label style={{ display: 'grid', gap: 6, marginBottom: 10 }}>
            <div style={{ fontSize: 13, opacity: 0.75 }}>Title</div>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{ padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
            />
          </label>

          <label style={{ display: 'grid', gap: 6, marginBottom: 12 }}>
            <div style={{ fontSize: 13, opacity: 0.75 }}>Subtitle</div>
            <input
              value={subtitle}
              onChange={(e) => setSubtitle(e.target.value)}
              style={{ padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
            />
          </label>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              onClick={() => onSave({ title: title.trim() || 'Untitled', subtitle })}
              className="btn btnPrimary"
            >
              Save
            </button>
            <button
              onClick={onDelete}
              className="btn"
              style={{ borderColor: '#fecaca' }}
            >
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default function KanbanApp() {
  const [state, dispatch] = useReducer(reducer, null, createInitialState)

  const columns = useMemo(() => {
    return state.columnOrder.map((colId) => {
      const col = state.columns[colId]
      const cards = col.cardIds.map((id) => state.cards[id]).filter(Boolean)
      return { id: col.id, title: col.title, cards }
    })
  }, [state])

  const selected = state.selectedCardId ? state.cards[state.selectedCardId] : null

  function addCard() {
    dispatch({ type: 'add', colId: 'todo', card: { title: 'New card', subtitle: '' } })
  }
  function saveCard(patch) {
    if (!state.selectedCardId) return
    dispatch({ type: 'update', cardId: state.selectedCardId, patch })
  }
  function deleteCard() {
    if (!state.selectedCardId) return
    dispatch({ type: 'delete', cardId: state.selectedCardId })
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr minmax(240px, 320px)', gap: 12, alignItems: 'start' }}>
      <div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
          <button onClick={addCard} className="btn btnPrimary">Add card</button>
          <div style={{ opacity: 0.75, fontSize: 13 }}>
            Click a card to edit • Empty columns show a hint
          </div>
        </div>

        <KanbanBoard
          columns={columns}
          onCardClick={(card) => dispatch({ type: 'select', cardId: card.id })}
        />
      </div>

      <Panel
        card={selected}
        onSave={saveCard}
        onDelete={deleteCard}
        onClose={() => dispatch({ type: 'select', cardId: null })}
      />
    </div>
  )
}
