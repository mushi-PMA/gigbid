import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useSession } from '../lib/session'
import { Icon, type IconName } from './Icon'

const links: { to: string; label: string; icon: IconName; end?: boolean }[] = [
  { to: '/', label: 'Inbox', icon: 'inbox', end: true },
  { to: '/approvals', label: 'Approvals', icon: 'approvals' },
  { to: '/pipeline', label: 'Pipeline', icon: 'pipeline' },
  { to: '/messages', label: 'Messages', icon: 'messages' },
  { to: '/analytics', label: 'Analytics', icon: 'analytics' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

export function Layout() {
  const { user, signOut } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  useEffect(() => setMenuOpen(false), [location.pathname])

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="sidebar">
        <div className="sidebar-top">
          <span className="brand">
            <span className="brand-mark" aria-hidden="true" />
            GigBid
          </span>
          <button type="button" className="menu-toggle ghost" aria-expanded={menuOpen} aria-controls="main-nav"
            onClick={() => setMenuOpen((open) => !open)}>
            <Icon name={menuOpen ? 'x' : 'menu'} />
            {menuOpen ? 'Close menu' : 'Menu'}
          </button>
        </div>
        <nav id="main-nav" aria-label="Main" className={menuOpen ? 'open' : ''}>
          <div className="nav-links">
            {links.map((link) => (
              <NavLink key={link.to} to={link.to} end={link.end}>
                <Icon name={link.icon} />
                {link.label}
              </NavLink>
            ))}
          </div>
          <div className="nav-foot">
            <div className="nav-user">
              <span className="avatar" aria-hidden="true">{(user?.display_name ?? '?').slice(0, 1).toUpperCase()}</span>
              <span className="nav-name">{user?.display_name}</span>
              <button type="button" className="icon-button" onClick={() => void signOut()} title="Sign out">
                <Icon name="signout" size={16} />
                <span className="sr-only">Sign out</span>
              </button>
            </div>
          </div>
        </nav>
      </header>
      <main id="main">
        <Outlet />
      </main>
    </div>
  )
}
