export default function KanbanCard({ card, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        textAlign: 'left',
        width: '100%',
        borderRadius: 12,
        padding: 12,
        background: '#fff',
        border: '1px solid #e5e7eb',
        cursor: 'pointer',
      }}
    >
      <div style={{ fontWeight: 650, marginBottom: 6 }}>{card.title}</div>
      {card.subtitle ? <div style={{ opacity: 0.75, fontSize: 13 }}>{card.subtitle}</div> : null}
    </button>
  )
}
