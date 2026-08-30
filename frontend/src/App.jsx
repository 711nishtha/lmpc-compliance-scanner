import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes, Link, useNavigate, useLocation } from 'react-router-dom'
import { getToken, getRole, clearSession } from './api/client'
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
      <div className="card error">
        The enforcement dashboard is admin-only. You're signed in as an inspector — use Scan or
        Repository instead, or log in with an admin account to view aggregate stats.
      </div>
    )
  }
  return children
}

function Nav() {
  const navigate = useNavigate()
  const location = useLocation()
  const authed = !!getToken()
  const isAdmin = getRole() === 'admin'
  // The landing page ships its own nav — don't stack the app chrome on top of it.
  if (location.pathname === '/') return null
  return (
    <nav className="nav">
      <div className="nav-brand">LMPC Compliance Scanner</div>
      {!authed && (
        <div className="nav-links">
          <ThemeToggle />
        </div>
      )}
      {authed && (
        <div className="nav-links">
          <Link to="/scan">Scan</Link>
          <Link to="/repository">Repository</Link>
          {isAdmin && <Link to="/dashboard">Dashboard</Link>}
          <span className="nav-role">{getRole()}</span>
          <ThemeToggle />
          <button
            className="link-btn"
            onClick={() => {
              clearSession()
              navigate('/login')
            }}
          >
            Log out
          </button>
        </div>
      )}
    </nav>
  )
}

function AppShellMain({ children }) {
  const location = useLocation()
  // Landing owns its own full-bleed layout; the app screens keep the padded container.
  if (location.pathname === '/') return children
  return <main className="main">{children}</main>
}

export default function App() {
  return (
    <div className="app-shell">
      <Nav />
      <AppShellMain>
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
      </AppShellMain>
    </div>
  )
}
