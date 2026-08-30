import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setSession } from '../api/client'

export default function Login() {
  const [email, setEmail] = useState('inspector@example.com')
  const [password, setPassword] = useState('password123')
  const [role, setRole] = useState('inspector')
  const [mode, setMode] = useState('login')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      const resp = mode === 'login' ? await api.login(email, password) : await api.register(email, password, role)
      setSession(resp.access_token, resp.role)
      navigate('/scan')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="card auth-card">
      <h1>Legal Metrology Compliance Scanner</h1>
      <p className="muted">SIH26034 — DoCA packaged-commodities compliance prototype</p>
      <form onSubmit={submit}>
        <label>Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        <label>Password</label>
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
        {mode === 'register' && (
          <>
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="inspector">Inspector</option>
              <option value="admin">Admin</option>
            </select>
          </>
        )}
        {error && <div className="error">{error}</div>}
        <button type="submit">{mode === 'login' ? 'Log in' : 'Register'}</button>
      </form>
      <button className="link-btn" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
        {mode === 'login' ? 'Need an account? Register' : 'Have an account? Log in'}
      </button>
    </div>
  )
}
