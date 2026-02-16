import { NavLink, Outlet } from 'react-router-dom'
import '../lib/ui.css'

export default function Layout() {
  const navClass = ({ isActive }) => (isActive ? 'navLink navLinkActive' : 'navLink')

  return (
    <div className="container">
      <header className="header">
        <div className="headerRow">
          <div>
            <h1 style={{ margin: 0, lineHeight: 1.15 }}>Nexus Lab Tracker</h1>
            <div className="subtitle">
              React UI with <code>/api/…</code> via Vite proxy → backend <code>127.0.0.1:8787</code>
            </div>
          </div>

          <nav className="nav">
            <NavLink to="/" end className={navClass}>Home</NavLink>
            <NavLink to="/demo" className={navClass}>Demo</NavLink>
            <NavLink to="/about" className={navClass}>About</NavLink>
          </nav>
        </div>
      </header>

      <main className="main">
        <Outlet />
      </main>

      <footer className="footer">
        Nexus Lab Tracker • UI baseline milestone (M2)
      </footer>
    </div>
  )
}
