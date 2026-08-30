import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.dashboardSummary().then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="card error">{error}</div>
  if (!data) return <div className="card">Loading…</div>

  const statuses = ['PASS', 'FAIL', 'NEEDS_VERIFICATION']

  return (
    <div className="card">
      <h2>Enforcement dashboard</h2>
      <div className="stat-row">
        <div className="stat-tile">
          <div className="stat-value">{data.total_scans}</div>
          <div className="stat-label">Total scans</div>
        </div>
        {statuses.map((s) => (
          <div className="stat-tile" key={s}>
            <div className="stat-value">{data.by_status[s] || 0}</div>
            <div className="stat-label">{s.replace('_', ' ')}</div>
          </div>
        ))}
      </div>

      <h3>Scans, last 30 days</h3>
      {data.trend_30d.length === 0 && <p className="muted">No scans in the last 30 days.</p>}
      <div className="trend-chart">
        {data.trend_30d.map((row) => (
          <div key={row.date} className="trend-bar-wrap" title={`${row.date}: ${row.count}`}>
            <div className="trend-bar" style={{ height: `${Math.max(4, row.count * 12)}px` }} />
            <div className="trend-label">{row.date.slice(5)}</div>
          </div>
        ))}
      </div>

      <h3>Recent non-compliant scans needing follow-up</h3>
      <table className="results-table">
        <thead>
          <tr>
            <th>Product</th>
            <th>Score</th>
            <th>Scanned</th>
          </tr>
        </thead>
        <tbody>
          {data.recent_noncompliant.map((s) => (
            <tr key={s.id}>
              <td>
                <Link to={`/scans/${s.id}`}>{s.product_name}</Link>
              </td>
              <td>{s.compliance_score != null ? `${s.compliance_score}%` : '—'}</td>
              <td>{new Date(s.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {data.recent_noncompliant.length === 0 && <p className="muted">No open non-compliance follow-ups.</p>}
    </div>
  )
}
