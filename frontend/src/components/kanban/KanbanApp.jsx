import { useMemo, useReducer, useState, useEffect } from 'react'
import { DndContext, PointerSensor, KeyboardSensor, useSensor, useSensors, closestCorners } from '@dnd-kit/core'
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable'
import KanbanBoard from './KanbanBoard.jsx'
import { createInitialState, reducer } from '../../lib/kanban/model.js'
import { loadBoard, saveBoard, clearBoard, validateBoard } from '../../lib/kanban/storage.js'

function Inspector({ card, onSave, onDelete, onClose }) {
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
        {ioErr ? <div style={{ color: 'crimson', fontSize: 13, marginTop: 8 }}>IO error: {ioErr}</div> : null}
        <div style={{ opacity: 0.75, fontSize: 13 }}>
          Select a card to edit it, or click “Add card”.
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
            <button onClick={() => onSave({ title: title.trim() || 'Untitled', subtitle })} className="btn btnPrimary">
              Save
            </button>
            <button onClick={onDelete} className="btn" style={{ borderColor: '#fecaca' }}>
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default function KanbanApp() {
  const [ioErr, setIoErr] = useState(null)
  const [state, dispatch] = useReducer(reducer, null, () => loadBoard() ?? createInitialState())

  // Debounced local persistence
  useEffect(() => {
    const t = setTimeout(() => { saveBoard(state) }, 350)
    return () => clearTimeout(t)
  }, [state])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  const selected = state.selectedCardId ? state.cards[state.selectedCardId] : null

  function findContainer(id) {
    if (!id) return null
    if (state.columns[id]) return id
    for (const colId of state.columnOrder) {
      if (state.columns[colId].cardIds.includes(id)) return colId
    }
    return null
  }

  function onDragEnd(event) {
    const { active, over } = event
    if (!over) return

    const activeId = String(active.id)
    const overId = String(over.id)

    const fromColId = findContainer(activeId)
    const toColId = findContainer(overId)

    if (!fromColId || !toColId) return
    if (fromColId === toColId && activeId === overId) return

    const toIds = state.columns[toColId].cardIds
    const toIndex = state.columns[toColId].cardIds.includes(overId)
      ? toIds.indexOf(overId)
      : toIds.length

    dispatch({ type: 'move', cardId: activeId, fromColId, toColId, toIndex })
  }

  function addCard() {
    dispatch({ type: 'add', colId: 'todo', card: { title: 'New card', subtitle: '' } })
  }
  function saveCard(patch) {
    if (!state.selectedCardId) return
    dispatch({ type: 'update', cardId: state.selectedCardId, patch })
  }
  function resetBoard() {
    const ok = confirm('Reset Kanban board? This clears local saved state.')
    if (!ok) return
    clearBoard()
    dispatch({ type: 'reset' })
  }
  async function exportBoard() {
    setIoErr(null)
    try {
      const payload = {
        columnOrder: state.columnOrder ?? [],
        columns: state.columns ?? {},
        cards: state.cards ?? {},
      }
      const text = JSON.stringify(payload, null, 2)
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
        alert('Board JSON copied to clipboard.')
      } else {
        prompt('Copy board JSON:', text)
      }
    } catch (e) {
      setIoErr(String(e?.message || e))
    }
  }

  function importBoard() {
    setIoErr(null)
    try {
      const raw = prompt('Paste board JSON to import:')
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (!validateBoard(parsed)) throw new Error('Invalid board JSON shape.')
      const payload = {
        columnOrder: parsed.columnOrder,
        columns: parsed.columns,
        cards: parsed.cards,
      }
      dispatch({ type: 'hydrate', state: payload })
      saveBoard(payload)
      alert('Imported board JSON.')
    } catch (e) {
      setIoErr(String(e?.message || e))
    }
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
          <button onClick={resetBoard} className="btn">Reset board</button>
          <button onClick={exportBoard} className="btn">Export JSON</button>
          <button onClick={importBoard} className="btn">Import JSON</button>
          <div style={{ opacity: 0.75, fontSize: 13 }}>
            Drag cards between columns • Click to edit in Inspector
          </div>
        </div>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragEnd={onDragEnd}
        >
          <KanbanBoard
            columnOrder={state.columnOrder}
            columnsById={state.columns}
            cardsById={state.cards}
            onCardClick={(c) => dispatch({ type: 'select', cardId: c.id })}
          />
        </DndContext>
      </div>

      <Inspector
        card={selected}
        onSave={saveCard}
        onDelete={deleteCard}
        onClose={() => dispatch({ type: 'select', cardId: null })}
      />
    </div>
  )
}
