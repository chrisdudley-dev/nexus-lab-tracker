import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

export default function KanbanCard({ card, onClick }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: card.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.7 : 1,
    textAlign: 'left',
    width: '100%',
    borderRadius: 12,
    padding: 12,
    background: '#fff',
    border: '1px solid #e5e7eb',
    cursor: 'grab',
  }

  return (
    <button
      ref={setNodeRef}
      type="button"
      onClick={onClick}
      style={style}
      {...attributes}
      {...listeners}
    >
      <div style={{ fontWeight: 650, marginBottom: 6 }}>{card.title}</div>
      {card.subtitle ? <div style={{ opacity: 0.75, fontSize: 13 }}>{card.subtitle}</div> : null}
    </button>
  )
}
