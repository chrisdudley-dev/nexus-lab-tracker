import KanbanColumn from './KanbanColumn.jsx'

export default function KanbanBoard({ columnOrder, columnsById, cardsById, onCardClick }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${columnOrder.length}, minmax(220px, 1fr))`, gap: 12 }}>
      {columnOrder.map((colId) => (
        <KanbanColumn
          key={colId}
          column={columnsById[colId]}
          cardsById={cardsById}
          onCardClick={onCardClick}
        />
      ))}
    </div>
  )
}
