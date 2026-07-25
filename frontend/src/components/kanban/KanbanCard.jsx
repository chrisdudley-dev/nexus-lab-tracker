import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

export default function KanbanCard({ card, onClick }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: card.id })

  const cardStyle = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.7 : 1,
    width: '100%',
    boxSizing: 'border-box',
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 8,
    alignItems: 'start',
    borderRadius: 12,
    padding: 8,
    background: '#fff',
    border: '1px solid #e5e7eb',
  }

  const editStyle = {
    minWidth: 0,
    padding: 4,
    border: 0,
    background: 'transparent',
    textAlign: 'left',
    cursor: 'pointer',
    touchAction: 'manipulation',
    userSelect: 'none',
    WebkitUserSelect: 'none',
  }

  const handleStyle = {
    padding: '4px 7px',
    border: '1px solid #d1d5db',
    borderRadius: 8,
    background: '#fff',
    cursor: 'grab',
    lineHeight: 1,
    minWidth: 44,
    minHeight: 44,
    display: 'grid',
    placeItems: 'center',
    touchAction: 'manipulation',
    userSelect: 'none',
    WebkitUserSelect: 'none',
  }

  const bodyTouchListeners = listeners?.onTouchStart
    ? { onTouchStart: listeners.onTouchStart }
    : {}

  return (
    <div ref={setNodeRef} style={cardStyle}>
      <button
        type="button"
        title="Tap to edit. Hold and drag to move."
        onClick={onClick}
        style={editStyle}
        {...bodyTouchListeners}
      >
        <div style={{ fontWeight: 650, marginBottom: 6 }}>{card.title}</div>
        {card.subtitle ? (
          <div style={{ opacity: 0.75, fontSize: 13 }}>{card.subtitle}</div>
        ) : null}
      </button>

      <button
        ref={setActivatorNodeRef}
        type="button"
        aria-label={`Move ${card.title}`}
        title="Drag or use the keyboard to move this card"
        style={handleStyle}
        {...attributes}
        {...listeners}
      >
        <span aria-hidden="true">⋮⋮</span>
      </button>
    </div>
  )
}
