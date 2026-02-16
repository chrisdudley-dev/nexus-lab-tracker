import { Link } from 'react-router-dom'

export default function Home() {
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Track samples through the lab workflow</h2>
      <p style={{ maxWidth: 720, lineHeight: 1.5, opacity: 0.9 }}>
        This project is a lightweight tracker for lab samples, built as a React UI + FastAPI backend.
        Use the Demo to exercise the end-to-end flows (health, auth/session, list/show, and status updates).
      </p>

      <div className="row" style={{ marginTop: 18 }}>
        <Link to="/demo" className="btn btnPrimary" style={{ textDecoration: 'none' }}>
          Open Demo
        </Link>
        <Link to="/about" className="btn" style={{ textDecoration: 'none', color: '#111' }}>
          How it works
        </Link>
      </div>
    </div>
  )
}
