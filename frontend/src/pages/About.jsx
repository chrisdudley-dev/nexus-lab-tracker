export default function About() {
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>About</h2>
      <p style={{ maxWidth: 760, lineHeight: 1.5, opacity: 0.9 }}>
        Nexus Lab Tracker is a demo-friendly app that shows a clean UI → API integration pattern.
        The frontend calls backend endpoints under <code>/api</code> via a Vite proxy.
      </p>

      <h3>Key features (high level)</h3>
      <ul style={{ lineHeight: 1.6, maxWidth: 760 }}>
        <li>Health/status visibility for the backend</li>
        <li>Sample list + details + events (read flow)</li>
        <li>Status updates (write flow)</li>
        <li>Session/auth guardrails for demo safety</li>
      </ul>

      <h3>Next milestones</h3>
      <ul style={{ lineHeight: 1.6, maxWidth: 760 }}>
        <li>M2: UI baseline polish (layout, responsive, clear entry point)</li>
        <li>M3: Kanban UX (board/columns/cards + interactions)</li>
        <li>M7: Public demo readiness (docs, walkthrough, screenshots)</li>
      </ul>
    </div>
  )
}
