import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, getToken, getRole } from '../api/client'
import { PageHead, StatusChip, formatWhen } from '../ui/Bits.jsx'

const ORDER = { FAIL: 0, NEEDS_VERIFICATION: 1, PASS: 2, NOT_APPLICABLE: 3 }

export default function ScanDetail() {
  const { id } = useParams()
  const [scan, setScan] = useState(null)
  const [error, setError] = useState('')
  const [imageUrl, setImageUrl] = useState(null)
  const [imageError, setImageError] = useState('')
  const [sortBySeverity, setSortBySeverity] = useState(true)

  const [verifyingRule, setVerifyingRule] = useState(null)
  const [verifyNote, setVerifyNote] = useState('')
  const [verifyError, setVerifyError] = useState('')
  const [verifyBusy, setVerifyBusy] = useState(false)
  const isAdmin = getRole() === 'admin'

  useEffect(() => {
    api.getScan(id).then(setScan).catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    let objectUrl = null
    fetch(api.scanImageUrl(id), { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((res) => { if (!res.ok) throw new Error('Annotated image not available'); return res.blob() })
      .then((blob) => { objectUrl = URL.createObjectURL(blob); setImageUrl(objectUrl) })
      .catch((e) => setImageError(e.message))
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [id])

  async function submitVerification(ruleId) {
    setVerifyBusy(true)
    setVerifyError('')
    try {
      // The endpoint returns the whole updated scan, so the recomputed score and overall status
      // land with the row change -- no second fetch, and no window where the header disagrees
      // with the findings under it.
      setScan(await api.verifyRuleResult(id, ruleId, verifyNote.trim() || null))
      setVerifyingRule(null)
      setVerifyNote('')
    } catch (e) {
      setVerifyError(e.message)
    } finally {
      setVerifyBusy(false)
    }
  }

  if (error) return <div className="panel panel-pad auth-error">{error}</div>
  if (!scan) return <div className="panel panel-pad empty">Loading…</div>

  const counts = scan.rule_results.reduce((acc, r) => {
    acc[r.status] = (acc[r.status] || 0) + 1
    return acc
  }, {})

  const rows = sortBySeverity
    ? [...scan.rule_results].sort((a, b) => (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9))
    : scan.rule_results

  return (
    <>
      <PageHead
        eyebrow={<>Record · <Link to="/repository" className="crumb">Repository</Link></>}
        title={scan.product_name}
        sub={`Scan #${String(scan.id).padStart(4, '0')} · ${formatWhen(scan.created_at)} · ${scan.inspector_email || 'unknown inspector'}`}
        actions={<StatusChip status={scan.overall_status} size="lg" />}
      />

      <div className="detail-top">
        {/* ---- Evidence ------------------------------------------------------ */}
        <section className="panel evidence">
          <div className="panel-head">
            <h2 className="panel-title">Annotated evidence</h2>
            <span className="panel-note">boxes mark located declarations</span>
          </div>
          {imageUrl ? (
            <img className="evidence-img" src={imageUrl}
                 alt={`Annotated photograph of the ${scan.product_name} label`} />
          ) : (
            <div className="empty">{imageError || 'Loading image…'}</div>
          )}
          <div className="legend">
            <span className="legend-item">
              <span className="legend-swatch" style={{ background: 'var(--color-status-pass)' }} />
              Located, compliant
            </span>
            <span className="legend-item">
              <span className="legend-swatch" style={{ background: 'var(--color-status-fail)' }} />
              Located, violation
            </span>
            <span className="legend-item legend-note">
              Rules the system could not decide are not drawn — a box would imply a precision the
              finding does not have.
            </span>
          </div>
        </section>

        {/* ---- Verdict ------------------------------------------------------- */}
        <aside className="panel">
          <div className="panel-head">
            <h2 className="panel-title">Determination</h2>
          </div>
          <div className="verdict">
            <div>
              <div className="verdict-score">
                {scan.compliance_score != null ? scan.compliance_score : '—'}
                <span className="unit">%</span>
              </div>
              <div className="readout-label" style={{ marginTop: 6 }}>Checks passed</div>
            </div>

            <div className="tally">
              {['PASS', 'FAIL', 'NEEDS_VERIFICATION', 'NOT_APPLICABLE'].map((s) => (
                counts[s] ? (
                  <div className="tally-row" key={s}>
                    <StatusChip status={s} />
                    <span className="num">{counts[s]}</span>
                  </div>
                ) : null
              ))}
            </div>

            <div className="meta-list">
              <div className="meta-row">
                <span className="meta-key">Ruleset</span>
                <span className="meta-val">{scan.ruleset_version}</span>
              </div>
              <div className="meta-row">
                <span className="meta-key">Font tier</span>
                <span className="meta-val">{scan.font_size_tier}</span>
              </div>
            </div>

            <div className="export-row">
              <a className="btn-inst btn-ghost btn-small" href={api.reportPdfUrl(scan.id)}
                 target="_blank" rel="noreferrer">PDF</a>
              <a className="btn-inst btn-ghost btn-small" href={api.reportDocxUrl(scan.id)}
                 target="_blank" rel="noreferrer">DOCX</a>
            </div>
          </div>
        </aside>
      </div>

      {/* ---- Findings -------------------------------------------------------- */}
      <section className="panel">
        <div className="panel-head">
          <h2 className="panel-title">Itemised findings</h2>
          <button type="button" className="sort-toggle"
                  onClick={() => setSortBySeverity((v) => !v)}>
            {sortBySeverity ? 'Sorted by severity' : 'Sorted by rule'} ⇅
          </button>
        </div>

        {rows.map((r) => (
          <article className="finding" key={r.rule_id} data-status={r.status}>
            <div>
              <div className="finding-id">{r.rule_id}</div>
              <div className="finding-ref">{r.rule_reference}</div>
            </div>

            <div>
              <p className="finding-req">{r.requirement_text}</p>
              {(r.evidence?.extracted_value || r.notes) && (
                <div className="finding-ev">
                  {r.evidence?.extracted_value && (
                    <div className="finding-quote">“{r.evidence.extracted_value}”</div>
                  )}
                  {r.notes && <p className="finding-notes">{r.notes}</p>}
                </div>
              )}
            </div>

            <div className="finding-side">
              <StatusChip status={r.status} />

              {r.evidence?.source && r.evidence.source !== 'ocr' && (
                <span className={`src-tag${r.evidence.source === 'ocr+vision' ? ' is-both' : ''}`}>
                  {r.evidence.source === 'ocr+vision' ? 'OCR + vision' : 'vision'}
                </span>
              )}

              {r.verified_by && (
                <div className="verified-note">
                  Verified by {r.verified_by}
                  <br />(automated: {r.original_status})
                </div>
              )}

              {isAdmin && r.status === 'NEEDS_VERIFICATION' && (
                verifyingRule === r.rule_id ? (
                  <div className="verify-form">
                    <label className="field-label" htmlFor={`n-${r.rule_id}`}>
                      What did you check?
                    </label>
                    <textarea
                      id={`n-${r.rule_id}`} className="inst-textarea" rows={3}
                      value={verifyNote} onChange={(e) => setVerifyNote(e.target.value)}
                      placeholder="e.g. Measured the MRP numeral at 2.2mm with a steel rule."
                    />
                    <div className="verify-actions">
                      <button type="button" className="btn-inst btn-small" disabled={verifyBusy}
                              onClick={() => submitVerification(r.rule_id)}>
                        {verifyBusy ? 'Saving…' : 'Confirm'}
                      </button>
                      <button type="button" className="btn-inst btn-ghost btn-small" disabled={verifyBusy}
                              onClick={() => { setVerifyingRule(null); setVerifyNote(''); setVerifyError('') }}>
                        Cancel
                      </button>
                    </div>
                    {verifyError && <div className="auth-error">{verifyError}</div>}
                  </div>
                ) : (
                  <button type="button" className="btn-inst btn-ghost btn-small"
                          onClick={() => { setVerifyingRule(r.rule_id); setVerifyNote(''); setVerifyError('') }}>
                    Mark verified
                  </button>
                )
              )}
            </div>
          </article>
        ))}
      </section>

      <p className="detail-foot">
        Font-size tier <strong>{scan.font_size_tier}</strong>. Items derived from a rule marked
        “VERIFY WITH DoCA” are never automatically passed or failed.
      </p>
    </>
  )
}
