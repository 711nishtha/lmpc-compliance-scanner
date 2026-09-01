import { Suspense, lazy } from 'react'
import { Navigate, NavLink, Route, Routes, Link, useNavigate, useLocation } from 'react-router-dom'
import { getToken, getRole, getEmail, clearSession } from './api/client'
import Login from './pages/Login.jsx'
import ThemeToggle from './theme/ThemeToggle.jsx'

// Lazy: keeps three/@react-three/fiber/gsap out of the authenticated app bundle.
const Landing = lazy(() => import('./landing/Landing.jsx'))
import Scan from './pages/Scan.jsx'
import ScanDetail from './pages/ScanDetail.jsx'
import Repository from './pages/Repository.jsx'
import Dashboard from './pages/Dashboard.jsx'

function RequireAuth({ children }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return children
}

function RequireAdmin({ children }) {
  if (!getToken()) return <Navigate to="/login" replace />
  if (getRole() !== 'admin') {
    return (
      <div className="panel panel-pad">
        <div className="page-eyebrow">Restricted</div>
        <h2 className="page-title" style={{ fontSize: '1.6rem' }}>Admin access required</h2>
        <p className="page-sub">
          The enforcement dashboard aggregates every inspector's findings, so it is admin-only.
          You're signed in as an inspector — use Scan or Repository instead.
        </p>
        <Link className="btn-inst" to="/scan" style={{ marginTop: 'var(--space-5)' }}>
          Go to Scan
        </Link>
      </div>
    )
  }
  return children
}

/* Icons are inline 1.4px-stroke line art rather than an icon font: the rail is
   the one place the app's line weight is visible at small size, and a webfont
   would also be a second network dependency for six glyphs. */
const ICONS = {
  scan: (
    <>
      <path d="M3 7V4.5A1.5 1.5 0 0 1 4.5 3H7M17 3h2.5A1.5 1.5 0 0 1 21 4.5V7M21 17v2.5a1.5 1.5 0 0 1-1.5 1.5H17M7 21H4.5A1.5 1.5 0 0 1 3 19.5V17" />
      <path d="M3 12h18" />
    </>
  ),
  repository: (
    <>
      <path d="M4 6.5C4 5.1 5.1 4 6.5 4H19v13H6.5A2.5 2.5 0 0 0 4 19.5z" />
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H19v3H6.5A2.5 2.5 0 0 1 4 19.5z" />
      <path d="M8 8h7M8 11h5" />
    </>
  ),
  dashboard: (
    <>
      <path d="M4 20V10M9.5 20V4M15 20v-7M20.5 20V7" />
    </>
  ),
}

function RailLink({ to, icon, label }) {
  return (
    <NavLink to={to} className={({ isActive }) => `rail-link${isActive ? ' is-active' : ''}`}>
      <svg className="rail-ico" viewBox="0 0 24 24" aria-hidden="true">{ICONS[icon]}</svg>
      <span>{label}</span>
    </NavLink>
  )
}

function Rail() {
  const navigate = useNavigate()
  const isAdmin = getRole() === 'admin'
  return (
    <aside className="rail">
      <Link to="/" className="rail-brand">
        <span className="rail-mark" aria-hidden="true" />
        <span className="rail-wordmark">
          LMPC
          <span>Compliance Scanner</span>
        </span>
      </Link>

      <nav className="rail-nav" aria-label="Main">
        <div className="rail-heading">Inspection</div>
        <RailLink to="/scan" icon="scan" label="Scan a label" />
        <RailLink to="/repository" icon="repository" label="Repository" />
        {isAdmin && (
          <>
            <div className="rail-heading" style={{ marginTop: 'var(--space-4)' }}>Oversight</div>
            <RailLink to="/dashboard" icon="dashboard" label="Enforcement" />
          </>
        )}
      </nav>

      {/* Fills the rail's long empty middle with something that earns its place:
          the ruleset the whole app is judging against, stated where an inspector
          can always see which edition their findings came from. */}
      <div className="rail-spacer" aria-hidden="true" />

      <div className="rail-foot">
        <div className="rail-ruleset">
          <span>Ruleset</span>
          LMPC 2011
          <em>as amended 2023 · G.S.R. 778(E)</em>
        </div>
        <div className="rail-id">
          <div className="rail-id-role">{getRole() || 'signed in'}</div>
          <div className="rail-id-email" title={getEmail() || ''}>{getEmail() || '—'}</div>
        </div>
        <div className="rail-actions">
          <ThemeToggle />
          <button
            type="button"
            className="btn-inst btn-ghost btn-small"
            onClick={() => {
              clearSession()
              navigate('/login')
            }}
          >
            Sign out
          </button>
        </div>
      </div>
    </aside>
  )
}

/* The landing page owns its own full-bleed chrome, and the login screen is a
   deliberate full-viewport composition -- neither may be wrapped in the rail. */
function Shell({ children }) {
  const location = useLocation()
  const bare = location.pathname === '/' || location.pathname === '/login' || !getToken()
  if (bare) return children
  return (
    <div className="inst-shell">
      <Rail />
      <main className="workspace">
        <div className="workspace-inner">{children}</div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route
          path="/"
          element={
            <Suspense fallback={<div className="route-loading" />}>
              <Landing />
            </Suspense>
          }
        />
        <Route path="/login" element={<Login />} />
        <Route path="/scan" element={<RequireAuth><Scan /></RequireAuth>} />
        <Route path="/scans/:id" element={<RequireAuth><ScanDetail /></RequireAuth>} />
        <Route path="/repository" element={<RequireAuth><Repository /></RequireAuth>} />
        <Route path="/dashboard" element={<RequireAdmin><Dashboard /></RequireAdmin>} />
        <Route path="*" element={<Navigate to={getToken() ? '/scan' : '/'} replace />} />
      </Routes>
    </Shell>
  )
}
