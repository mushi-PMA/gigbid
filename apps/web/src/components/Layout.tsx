import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useSession } from '../lib/session'

const links = [
  { to: '/', label: 'Inbox', end: true },
  { to: '/approvals', label: 'Approvals' },
  { to: '/pipeline', label: 'Pipeline' },
  { to: '/messages', label: 'Messages' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/settings', label: 'Settings' },
]

export function Layout() {
  const { user, signOut } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  useEffect(() => setMenuOpen(false), [location.pathname])

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <span className="brand">GigBid</span>
        <button
          type="button"
          className="menu-toggle"
          aria-expanded={menuOpen}
          aria-controls="main-nav"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? 'Close menu' : 'Menu'}
        </button>
        <nav id="main-nav" aria-label="Main" className={menuOpen ? 'open' : ''}>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}>
              {link.label}
            </NavLink>
          ))}
          <span className="nav-user">
            <span className="muted">{user?.display_name}</span>
            <button type="button" className="link-button" onClick={() => void signOut()}>
              Sign out
            </button>
          </span>
        </nav>
      </header>
      <main id="main">
        <Outlet />
      </main>
    </>
  )
}
