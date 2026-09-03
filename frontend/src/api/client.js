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
const EMAIL_KEY = 'lmpc_email'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setSession(token, role, email) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(ROLE_KEY, role)
  // Shown on the rail's identity plate. The API returns only a token and role, and decoding the
  // JWT client-side just to recover the address it was issued for would be more moving parts
  // than storing what the user already typed.
  if (email) localStorage.setItem(EMAIL_KEY, email)
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(ROLE_KEY)
  localStorage.removeItem(EMAIL_KEY)
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY)
}

export function getEmail() {
  return localStorage.getItem(EMAIL_KEY)
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
    // `detail` is usually a plain string, but a few endpoints (scans.py's IMAGE_QUALITY_INSUFFICIENT
    // gate) return a structured object instead, so a caller can branch on `.code` rather than
    // pattern-matching error text. Keep `err.message` a sane string either way (never
    // "[object Object]"), and expose the structured body separately for callers that want it.
    const structured = detail && typeof detail === 'object' ? detail : null
    const err = new Error(structured ? structured.message || res.statusText : detail)
    err.detail = structured
    err.status = res.status
    throw err
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
  // Admin-only. Resolves a NEEDS_VERIFICATION result to PASS after a person has checked the
  // physical package; the backend refuses anything that is not currently NEEDS_VERIFICATION.
  verifyRuleResult: (scanId, ruleId, note) =>
    request(`/scans/${scanId}/rule-results/${encodeURIComponent(ruleId)}/verify`, {
      method: 'POST',
      json: { note },
    }),
  createScan: (formData) => request('/scans', { method: 'POST', body: formData }),
  dashboardSummary: () => request('/dashboard/summary'),
  // Reports are auth-gated (app/api/reports.py depends on get_current_user), so they CANNOT be
  // opened with a plain <a href>: a browser navigation carries no Authorization header, so the
  // link just landed on the backend URL and 401'd. Fetch the bytes with the token, then hand the
  // browser a blob to save -- the same approach ScanDetail already uses for the annotated image.
  downloadReport: async (id, kind) => {
    const blob = await request(`/reports/${id}/${kind}`)
    // Filename is constructed here rather than read from Content-Disposition: that header is not
    // readable cross-origin unless the server adds it to Access-Control-Expose-Headers, and this
    // matches the name the backend sets.
    const filename = `compliance_report_${id}.${kind}`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    // Revoked on the next tick, not immediately: revoking synchronously after click() can beat
    // the browser to reading the blob in some engines.
    setTimeout(() => URL.revokeObjectURL(url), 0)
  },
  scanImageUrl: (id) => `${API_BASE}/api/scans/${id}/image`,
}
