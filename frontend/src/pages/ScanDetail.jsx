import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, getToken } from '../api/client'

const STATUS_CLASS = {
  PASS: 'status-pass',
  FAIL: 'status-fail',
  NEEDS_VERIFICATION: 'status-verify',
  NOT_APPLICABLE: 'status-na',
}

export default function ScanDetail() {
  const { id } = useParams()
  const [scan, setScan] = useState(null)
  const [error, setError] = useState('')
  const [imageUrl, setImageUrl] = useState(null)
  const [imageError, setImageError] = useState('')

  useEffect(() => {
    api.getScan(id).then(setScan).catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    let objectUrl = null
    fetch(api.scanImageUrl(id), { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((res) => {
        if (!res.ok) throw new Error('Annotated image not available')
        return res.blob()
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        setImageUrl(objectUrl)
      })
      .catch((e) => setImageError(e.message))
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [id])

  if (error) return <div className="card error">{error}</div>
  if (!scan) return <div className="card">Loading…</div>

  const passCount = scan.rule_results.filter((r) => r.status === 'PASS').length
  const failCount = scan.rule_results.filter((r) => r.status === 'FAIL').length
  const verifyCount = scan.rule_results.filter((r) => r.status === 'NEEDS_VERIFICATION').length

  async function download(kind) {
    const url = kind === 'pdf' ? api.reportPdfUrl(scan.id) : api.reportDocxUrl(scan.id)
    const res = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
    const blob = await res.blob()
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `compliance_report_${scan.id}.${kind}`
    link.click()
  }

  return (
    <div className="card">
      <h2>{scan.product_name}</h2>
      <div className={`overall-badge ${STATUS_CLASS[scan.overall_status]}`}>{scan.overall_status}</div>
      {scan.declarations?.image_quality_warning && (
        <div className="quality-banner">
          <strong>⚠ Possible bad photo, not a bad product:</strong> {scan.declarations.image_quality_warning}
        </div>
      )}
      <p className="muted">
        Ruleset {scan.ruleset_version} · Scanned {new Date(scan.created_at).toLocaleString()} · Inspector: {scan.inspector_email}
      </p>
      <p className="muted small">
        Secondary summary metric: {passCount} PASS, {failCount} FAIL, {verifyCount} NEEDS VERIFICATION
        {scan.compliance_score != null && ` (${scan.compliance_score}% of applicable checks passed)`}.
        The itemized results below are the primary output.
      </p>
      <div className="actions">
        <button onClick={() => download('pdf')}>Download PDF report</button>
        <button onClick={() => download('docx')}>Download editable DOCX</button>
      </div>

      <h3>Annotated label</h3>
      {imageUrl && (
        <div className="annotated-image-wrap">
          {/* The annotated image IS the primary evidence, so its alt text carries the actual
              findings rather than describing the picture — a screen-reader user cannot see the
              boxes, and "annotated scan" tells them nothing. The itemised table below is the
              full accessible equivalent. */}
          <img
            className="annotated-image"
            src={imageUrl}
            alt={
              `Scan of ${scan.product_name} with each detected declaration outlined and ` +
              `labelled by rule: ${passCount} passed, ${failCount} failed, ` +
              `${verifyCount} need verification. Full itemised results follow in the table below.`
            }
          />
          <div className="annotated-legend">
            <span className="legend-item"><span className="legend-swatch status-pass" /> PASS</span>
            <span className="legend-item"><span className="legend-swatch status-fail" /> FAIL</span>
            <span className="legend-item"><span className="legend-swatch status-verify" /> NEEDS VERIFICATION</span>
          </div>
        </div>
      )}
      {!imageUrl && imageError && <p className="muted small">{imageError}</p>}
      {!imageUrl && !imageError && <p className="muted small">Loading annotated image…</p>}

      <h3>Itemized rule-cited results</h3>
      <table className="results-table">
        <thead>
          <tr>
            <th>Rule</th>
            <th>Requirement</th>
            <th>Status</th>
            <th>Evidence / Notes</th>
          </tr>
        </thead>
        <tbody>
          {scan.rule_results.map((r) => (
            <tr key={r.rule_id}>
              <td>
                <strong>{r.rule_id}</strong>
                <div className="muted small">{r.rule_reference}</div>
              </td>
              <td>{r.requirement_text}</td>
              <td>
                <span className={`badge ${STATUS_CLASS[r.status]}`}>{r.status}</span>
              </td>
              <td>
                {r.evidence?.extracted_value && <div>"{r.evidence.extracted_value}"</div>}
                {r.notes && <div className="muted small">{r.notes}</div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        Font-size tier used: <strong>{scan.font_size_tier}</strong>. Items derived from a rule
        marked "VERIFY WITH DoCA" in LEGAL_REQUIREMENTS.md are never auto PASS/FAIL.
      </p>
    </div>
  )
}
