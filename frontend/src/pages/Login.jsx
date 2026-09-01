import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setSession } from '../api/client'
import ThemeToggle from '../theme/ThemeToggle.jsx'

/* Specimen readings that sweep through the left panel. These are the real
   declarations this tool checks and the real rule numbers behind them -- the
   panel is a demonstration of the product, not decorative lorem. */
const SPECIMENS = [
  { field: 'NET QTY.', value: '57 g', rule: 'Rule 6(1)(c)' },
  { field: 'MRP', value: 'Rs. 25.00', rule: 'Rule 6(1)(e)' },
  { field: 'PKD.', value: '17/06/26', rule: 'Rule 6(1)(d)' },
  { field: 'USE BY', value: '14/03/27', rule: 'Rule 6(1)(da)' },
  { field: 'MFR.', value: 'DFM Foods Limited', rule: 'Rule 6(1)(a)' },
  { field: 'UNIT PRICE', value: 'Rs. 0.44/g', rule: 'Rule 6, 2023 amd.' },
]

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('inspector')
  const [mode, setMode] = useState('login')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [cursor, setCursor] = useState(0)
  const navigate = useNavigate()
  const emailRef = useRef(null)

  useEffect(() => { emailRef.current?.focus() }, [])

  useEffect(() => {
    const t = setInterval(() => setCursor((c) => (c + 1) % SPECIMENS.length), 2600)
    return () => clearInterval(t)
  }, [])

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const resp = mode === 'login'
        ? await api.login(email, password)
        : await api.register(email, password, role)
      setSession(resp.access_token, resp.role, email)
      navigate('/scan')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <div className="auth-toggle"><ThemeToggle /></div>

      {/* ---- Left: the instrument at work ---------------------------------- */}
      <section className="auth-stage" aria-hidden="true">
        <div className="auth-stage-grid" />
        <div className="auth-stage-inner">
          <div className="auth-mark">
            <span className="auth-mark-box" />
            <span>
              LMPC
              <em>Legal Metrology Compliance</em>
            </span>
          </div>

          <p className="auth-stage-lead">
            Every declaration on a package,<br />checked against the rule that requires it.
          </p>

          <div className="auth-specimen bracket">
            <div className="auth-specimen-scan" />
            <ul className="auth-specimen-list">
              {SPECIMENS.map((s, i) => (
                <li key={s.field} className={i === cursor ? 'is-live' : ''}>
                  <span className="sp-field">{s.field}</span>
                  <span className="sp-value">{s.value}</span>
                  <span className="sp-rule">{s.rule}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="auth-stage-foot">
            <span>SIH26034</span>
            <span className="dot" />
            <span>Department of Consumer Affairs</span>
            <span className="dot" />
            <span>Rules of 2011</span>
          </div>
        </div>
      </section>

      {/* ---- Right: the form ---------------------------------------------- */}
      <section className="auth-panel">
        <div className="auth-form-wrap">
          <div className="page-eyebrow">{mode === 'login' ? 'Secure sign in' : 'New account'}</div>
          <h1 className="auth-title">
            {mode === 'login' ? 'Open the console' : 'Register an inspector'}
          </h1>
          <p className="auth-lead">
            {mode === 'login'
              ? 'Sign in to scan package labels and review inspection findings.'
              : 'Create credentials for field inspection or enforcement oversight.'}
          </p>

          <form onSubmit={submit} className="auth-form" noValidate={false}>
            <div className="field">
              <label className="field-label" htmlFor="auth-email">Email</label>
              <input
                id="auth-email" ref={emailRef} className="inst-input" type="email" required
                autoComplete="username" placeholder="inspector@doca.gov.in"
                value={email} onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field-label" htmlFor="auth-pass">Password</label>
              <input
                id="auth-pass" className="inst-input" type="password" required
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                placeholder="••••••••••"
                value={password} onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {mode === 'register' && (
              <div className="field">
                <span className="field-label">Role</span>
                {/* Radio cards rather than a select: the two roles have genuinely
                    different powers (only admin can verify a finding), so the
                    difference is worth stating at the point of choosing. */}
                <div className="role-picker">
                  {[
                    { id: 'inspector', name: 'Inspector', desc: 'Scan labels, review findings' },
                    { id: 'admin', name: 'Admin', desc: 'Also: oversight, verify findings' },
                  ].map((r) => (
                    <label key={r.id} className={`role-card${role === r.id ? ' is-on' : ''}`}>
                      <input
                        type="radio" name="role" value={r.id}
                        checked={role === r.id} onChange={() => setRole(r.id)}
                      />
                      <span className="role-name">{r.name}</span>
                      <span className="role-desc">{r.desc}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {error && <div className="auth-error" role="alert">{error}</div>}

            <button className="btn-inst auth-submit" type="submit" disabled={busy}>
              {busy ? 'Verifying…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <button
            type="button"
            className="auth-switch"
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
          >
            {mode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in'}
          </button>
        </div>

        <div className="auth-panel-foot">
          <span>SIH26034</span>
          <span>·</span>
          <span>Prototype build</span>
        </div>
      </section>
    </div>
  )
}
