import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { PageHead, ScoreCell, StatusChip, Empty, formatWhen } from '../ui/Bits.jsx'

const STATUSES = ['PASS', 'FAIL', 'NEEDS_VERIFICATION']

export default function Repository() {
  const [scans, setScans] = useState([])
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load(overrides = {}) {
    setLoading(true)
    setError('')
    const state = { q, statusFilter, dateFrom, dateTo, ...overrides }
    try {
      const params = {}
      if (state.q) params.q = state.q
      if (state.statusFilter) params.status_filter = state.statusFilter
      if (state.dateFrom) params.date_from = state.dateFrom
      if (state.dateTo) params.date_to = state.dateTo
      setScans(await api.listScans(params))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Status is a one-click toggle rather than a dropdown + Search press: it is the
  // filter an inspector reaches for constantly, and it applies immediately so the
  // register behaves like a control surface, not a form to submit.
  function toggleStatus(s) {
    const next = statusFilter === s ? '' : s
    setStatusFilter(next)
    load({ statusFilter: next })
  }

  function reset() {
    setQ(''); setStatusFilter(''); setDateFrom(''); setDateTo('')
    load({ q: '', statusFilter: '', dateFrom: '', dateTo: '' })
  }

  const active = q || statusFilter || dateFrom || dateTo

  return (
    <>
      <PageHead
        eyebrow="Inspection register"
        title="Scanned products"
        sub="Every scan ever run, with the determination it produced. Open a record for its itemised, rule-cited findings and the annotated label."
        actions={<Link className="btn-inst" to="/scan">New scan</Link>}
      />

      <section className="panel">
        <div className="filter-bar">
          <div className="field">
            <label className="field-label" htmlFor="rq">Product</label>
            <input
              id="rq" className="inst-input" placeholder="Search by name…"
              value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && load()}
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="rf">Scanned from</label>
            <input id="rf" className="inst-input" type="date"
                   value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="rt">Scanned to</label>
            <input id="rt" className="inst-input" type="date"
                   value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">&nbsp;</span>
            <button className="btn-inst" type="button" onClick={() => load()}>Apply</button>
          </div>
          <div className="field">
            <span className="field-label">&nbsp;</span>
            <button className="btn-inst btn-ghost" type="button" onClick={reset} disabled={!active}>
              Reset
            </button>
          </div>
        </div>

        <div className="chip-row">
          <span className="chip-row-label">Determination</span>
          {STATUSES.map((s) => (
            <button
              key={s} type="button"
              className={`filter-chip${statusFilter === s ? ' is-on' : ''}`}
              aria-pressed={statusFilter === s}
              onClick={() => toggleStatus(s)}
            >
              <StatusChip status={s} />
            </button>
          ))}
          <span className="chip-row-count">
            {loading ? 'loading…' : `${scans.length} record${scans.length === 1 ? '' : 's'}`}
          </span>
        </div>

        {error && <div className="panel-pad"><div className="auth-error">{error}</div></div>}

        {!loading && scans.length === 0 ? (
          <Empty
            title={active ? 'No records match those filters' : 'No scans yet'}
            hint={active
              ? 'Try widening the date range or clearing the determination filter.'
              : 'Scan a package label to start the inspection register.'}
            action={active
              ? <button className="btn-inst btn-ghost btn-small" onClick={reset}>Clear filters</button>
              : <Link className="btn-inst btn-small" to="/scan">Scan a label</Link>}
          />
        ) : (
          <div className="table-wrap">
            <table className="ledger">
              <thead>
                <tr>
                  <th>Product</th>
                  <th style={{ width: 150 }}>Determination</th>
                  <th style={{ width: 180 }}>Compliance</th>
                  <th style={{ width: 190 }}>Scanned</th>
                  <th style={{ width: 210 }}>Inspector</th>
                  <th style={{ width: 84 }} />
                </tr>
              </thead>
              <tbody>
                {scans.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <Link className="ledger-primary" to={`/scans/${s.id}`}>{s.product_name}</Link>
                      <div className="ledger-meta">SCAN #{String(s.id).padStart(4, '0')}</div>
                    </td>
                    <td><StatusChip status={s.overall_status} /></td>
                    <td><ScoreCell score={s.compliance_score} /></td>
                    <td className="num">{formatWhen(s.created_at)}</td>
                    <td className="ledger-inspector">{s.inspector_email || '—'}</td>
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
