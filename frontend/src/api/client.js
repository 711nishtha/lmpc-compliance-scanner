/* API base URL.
 *
 * Local dev: empty string, so requests stay same-origin ("/api/...") and Vite's dev
 * proxy forwards them to the backend on :8000.
 * Production: VITE_API_BASE_URL is baked in at build time (Render Static Site env var),
 * e.g. "https://lmpc-backend.onrender.com" — a static host has no proxy, so without
 * this every call would 404 against the static site's own origin.
 *
 * Trailing slashes are stripped so the caller can always join with "/api/...".
 */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

const TOKEN_KEY = 'lmpc_token'
const ROLE_KEY = 'lmpc_role'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setSession(token, role) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(ROLE_KEY, role)
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(ROLE_KEY)
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY)
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (options.json) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(options.json)
  }
  const res = await fetch(`${API_BASE}/api${path}`, { ...options, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail)
  }
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) return res.json()
  return res.blob()
}

export const api = {
  register: (email, password, role) => request('/auth/register', { method: 'POST', json: { email, password, role } }),
  login: (email, password) => request('/auth/login', { method: 'POST', json: { email, password } }),
  listScans: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/scans${qs ? `?${qs}` : ''}`)
  },
  getScan: (id) => request(`/scans/${id}`),
  createScan: (formData) => request('/scans', { method: 'POST', body: formData }),
  dashboardSummary: () => request('/dashboard/summary'),
  reportPdfUrl: (id) => `${API_BASE}/api/reports/${id}/pdf`,
  reportDocxUrl: (id) => `${API_BASE}/api/reports/${id}/docx`,
  scanImageUrl: (id) => `${API_BASE}/api/scans/${id}/image`,
}
