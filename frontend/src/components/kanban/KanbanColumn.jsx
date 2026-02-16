import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import KanbanCard from './KanbanCard.jsx'

export default function KanbanColumn({ column, cardsById, onCardClick }) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id })

  return (
    <div
      ref={setNodeRef}
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: 12,
        padding: 12,
        background: isOver ? '#f9fafb' : '#fff',
        minHeight: 120,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontWeight: 700 }}>{column.title}</div>
        <div style={{ opacity: 0.7, fontSize: 12 }}>{column.cardIds.length}</div>
      </div>

      <SortableContext items={column.cardIds} strategy={verticalListSortingStrategy}>
        <div style={{ display: 'grid', gap: 10 }}>
          {column.cardIds.map((id) => {
            const card = cardsById[id]
            if (!card) return null
            return <KanbanCard key={id} card={card} onClick={() => onCardClick?.(card)} />
          })}
          {column.cardIds.length === 0 ? (
            <div style={{ opacity: 0.65, fontSize: 13, padding: 10, border: '1px dashed #e5e7eb', borderRadius: 10 }}>
              Drop a card here
            </div>
          ) : null}
        </div>
      </SortableContext>
    </div>
  )
}
