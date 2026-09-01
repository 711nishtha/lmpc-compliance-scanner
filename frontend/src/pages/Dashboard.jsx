import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { PageHead, ScoreCell, StatusChip, Empty, formatWhen } from '../ui/Bits.jsx'

/* Fills a contiguous day-by-day window ending today, so gaps in the API's
   sparse result show up as gaps rather than being closed silently. */
function buildWindow(rows, days) {
  const counts = new Map(rows.map((r) => [r.date, r.count]))
  const out = []
  const cursor = new Date()
  cursor.setHours(0, 0, 0, 0)
  cursor.setDate(cursor.getDate() - (days - 1))
  for (let i = 0; i < days; i += 1) {
    const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}-${String(cursor.getDate()).padStart(2, '0')}`
    out.push({ date: key, count: counts.get(key) || 0 })
    cursor.setDate(cursor.getDate() + 1)
  }
  return out
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.dashboardSummary().then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="panel panel-pad auth-error">{error}</div>
  if (!data) return <div className="panel panel-pad empty">Loading…</div>

  const pass = data.by_status.PASS || 0
  const fail = data.by_status.FAIL || 0
  const verify = data.by_status.NEEDS_VERIFICATION || 0
  const total = data.total_scans || 0
  const decided = pass + fail
  // "Clearance rate" is deliberately computed over DECIDED scans only. Folding
  // NEEDS_VERIFICATION into the denominator would let an unreadable batch of
  // photos drag the number down as though those packages had failed, which is
  // the same conflation of "could not determine" with "non-compliant" the rule
  // engine refuses to make.
  const clearance = decided ? Math.round((pass / decided) * 100) : null

  const trendTotal = data.trend_30d.reduce((n, r) => n + r.count, 0)
  // The API returns only days that HAVE scans, so a burst of activity on one day
  // rendered as a single block filling the whole panel -- which reads as "every
  // day was busy", the opposite of the truth. Pad the window to a real 30-day
  // series so empty days are visible as empty.
  const series = buildWindow(data.trend_30d, 30)
  const peak = Math.max(1, ...series.map((r) => r.count))

  return (
    <>
      <PageHead
        eyebrow="Enforcement oversight"
        title="Inspection posture"
        sub="Aggregate findings across every inspector. Figures summarise machine determinations; each one remains traceable to the cited rule on its own scan."
      />

      <div className="readout-grid" style={{ marginBottom: 'var(--space-5)' }}>
        <div className="readout">
          <div className="readout-label">Total scans</div>
          <div className="readout-value">{total}</div>
          <div className="readout-foot">{trendTotal} in the last 30 days</div>
        </div>
        <div className="readout" data-status="PASS">
          <div className="readout-label">Compliant</div>
          <div className="readout-value">{pass}</div>
          <div className="readout-foot">Every Rule 6–8 check passed</div>
        </div>
        <div className="readout" data-status="FAIL">
          <div className="readout-label">Non-compliant</div>
          <div className="readout-value">{fail}</div>
          <div className="readout-foot">At least one cited violation</div>
        </div>
        <div className="readout" data-status="VERIFY">
          <div className="readout-label">Needs verification</div>
          <div className="readout-value">{verify}</div>
          <div className="readout-foot">Awaiting a human check</div>
        </div>
      </div>

      <div className="dash-split">
        {/* ---- Distribution -------------------------------------------------- */}
        <section className="panel">
          <div className="panel-head">
            <h2 className="panel-title">Distribution</h2>
            <span className="panel-note">
              {clearance == null ? 'no decided scans' : `${clearance}% clearance of decided`}
            </span>
          </div>
          <div className="panel-pad">
            <div className="dist-bar" role="img"
                 aria-label={`${pass} compliant, ${fail} non-compliant, ${verify} needing verification`}>
              {[
                ['PASS', pass, 'var(--color-status-pass)'],
                ['FAIL', fail, 'var(--color-status-fail)'],
                ['NEEDS_VERIFICATION', verify, 'var(--color-status-verify)'],
              ].map(([k, n, c]) => n > 0 && (
                <span key={k} className="dist-seg"
                      style={{ flexGrow: n, background: c }} title={`${k}: ${n}`} />
              ))}
              {total === 0 && <span className="dist-seg dist-empty" style={{ flexGrow: 1 }} />}
            </div>
            <ul className="dist-key">
              {[
                ['PASS', pass], ['FAIL', fail], ['NEEDS_VERIFICATION', verify],
              ].map(([k, n]) => (
                <li key={k}>
                  <StatusChip status={k} />
                  <span className="num">{n}</span>
                  <span className="dist-pct">{total ? Math.round((n / total) * 100) : 0}%</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ---- Trend --------------------------------------------------------- */}
        <section className="panel">
          <div className="panel-head">
            <h2 className="panel-title">Scan volume · 30 days</h2>
            <span className="panel-note">peak {peak}/day</span>
          </div>
          {data.trend_30d.length === 0 ? (
            <Empty title="No scans in the last 30 days" hint="Scan a label to start the record." />
          ) : (
            <>
              <div className="chart">
                {series.map((row) => (
                  <div className="chart-col" key={row.date}
                       title={`${row.date}: ${row.count} scan${row.count === 1 ? '' : 's'}`}>
                    <div className={`chart-bar${row.count === 0 ? ' is-zero' : ''}`}
                         style={{ height: row.count ? `${(row.count / peak) * 100}%` : '2px' }} />
                  </div>
                ))}
              </div>
              <div className="chart-axis">
                <span>{series[0]?.date.slice(5)}</span>
                <span>today</span>
              </div>
            </>
          )}
        </section>
      </div>

      {/* ---- Follow-up queue ------------------------------------------------- */}
      <section className="panel" style={{ marginTop: 'var(--space-5)' }}>
        <div className="panel-head">
          <h2 className="panel-title">Open follow-ups</h2>
          <span className="panel-note">non-compliant, most recent first</span>
        </div>
        {data.recent_noncompliant.length === 0 ? (
          <Empty title="Nothing outstanding" hint="No scan currently carries an open violation." />
        ) : (
          <div className="table-wrap">
            <table className="ledger">
              <thead>
                <tr>
                  <th>Product</th>
                  <th style={{ width: 190 }}>Compliance</th>
                  <th style={{ width: 200 }}>Scanned</th>
                  <th style={{ width: 90 }} />
                </tr>
              </thead>
              <tbody>
                {data.recent_noncompliant.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <Link className="ledger-primary" to={`/scans/${s.id}`}>{s.product_name}</Link>
                      <div className="ledger-meta">SCAN #{String(s.id).padStart(4, '0')}</div>
                    </td>
                    <td><ScoreCell score={s.compliance_score} /></td>
                    <td className="num">{formatWhen(s.created_at)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <Link className="row-open" to={`/scans/${s.id}`}>Open →</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
