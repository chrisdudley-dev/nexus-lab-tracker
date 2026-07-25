import KanbanColumn from './KanbanColumn.jsx'

export default function KanbanBoard({ columnOrder, columnsById, cardsById, onCardClick }) {
  return (
    <div
      className="kanbanBoard"
      style={{ gridTemplateColumns: `repeat(${columnOrder.length}, minmax(220px, clamp(220px, 24vw, 280px)))` }}
    >
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
