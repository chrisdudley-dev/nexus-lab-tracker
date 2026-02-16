import KanbanCard from './KanbanCard.jsx'

export default function KanbanColumn({ column, onCardClick }) {
  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 12, background: '#fff' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontWeight: 700 }}>{column.title}</div>
        <div style={{ opacity: 0.7, fontSize: 12 }}>{column.cards.length}</div>
      </div>

      <div style={{ display: 'grid', gap: 10 }}>
        {column.cards.map((card) => (
          <KanbanCard key={card.id} card={card} onClick={() => onCardClick?.(card)} />
        ))}
        {column.cards.length === 0 ? (
          <div style={{ opacity: 0.65, fontSize: 13, padding: 10, border: '1px dashed #e5e7eb', borderRadius: 10 }}>
            No cards
          </div>
        ) : null}
      </div>
    </div>
  )
}
