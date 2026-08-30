import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export default function Repository() {
  const [scans, setScans] = useState([])
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [error, setError] = useState('')

  async function load() {
    try {
      const params = {}
      if (q) params.q = q
      if (statusFilter) params.status_filter = statusFilter
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      setScans(await api.listScans(params))
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="card">
      <h2>Scanned products &amp; inspection history</h2>
      <div className="form-row">
        <input placeholder="Search product name…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">Any status</option>
          <option value="PASS">PASS</option>
          <option value="FAIL">FAIL</option>
          <option value="NEEDS_VERIFICATION">NEEDS VERIFICATION</option>
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <button onClick={load}>Search</button>
      </div>
      {error && <div className="error">{error}</div>}
      <table className="results-table">
        <thead>
          <tr>
            <th>Product</th>
            <th>Status</th>
            <th>Score</th>
            <th>Scanned</th>
            <th>Inspector</th>
          </tr>
        </thead>
        <tbody>
          {scans.map((s) => (
            <tr key={s.id}>
              <td>
                <Link to={`/scans/${s.id}`}>{s.product_name}</Link>
              </td>
              <td>{s.overall_status}</td>
              <td>{s.compliance_score != null ? `${s.compliance_score}%` : '—'}</td>
              <td>{new Date(s.created_at).toLocaleString()}</td>
              <td>{s.inspector_email}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {scans.length === 0 && <p className="muted">No scans yet. Scan a product to get started.</p>}
    </div>
  )
}
