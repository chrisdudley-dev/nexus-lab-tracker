import KanbanColumn from './KanbanColumn.jsx'

export default function KanbanBoard({ columns, onCardClick }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${columns.length}, minmax(220px, 1fr))`, gap: 12 }}>
      {columns.map((col) => (
        <KanbanColumn key={col.id} column={col} onCardClick={onCardClick} />
      ))}
    </div>
  )
}
