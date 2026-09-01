import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

// A scan is one synchronous request -- the backend doesn't stream real progress events, so a
// bar claiming an exact percentage would be exactly the kind of fabricated certainty this
// project refuses to produce elsewhere. Instead: an indeterminate bar (genuinely "still
// working", not "N% done"), paired with captions timed off what the pipeline actually does and
// how long each stage really takes on a real photo (measured this build cycle -- OCR alone is
// 1-5s, the dual-pass ensemble roughly doubles that). Purely informational UI texture, not a
// claim about progress -- if this drifts from reality, update the thresholds, not the disclaimer.
const SCAN_STAGES = [
  { afterMs: 0, label: 'Uploading photo…' },
  { afterMs: 900, label: 'Checking image quality…' },
  { afterMs: 2200, label: 'Reading the label (OCR)…' },
  { afterMs: 7000, label: 'Extracting declarations…' },
  { afterMs: 9000, label: 'Checking against Rule 6, 7 & 8…' },
  { afterMs: 11000, label: 'Still working — busy or multilingual labels take longer…' },
]

export default function Scan() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [productName, setProductName] = useState('')
  const [category, setCategory] = useState('')
  const [isImported, setIsImported] = useState('')
  const [isPerishable, setIsPerishable] = useState('')
  const [refWidth, setRefWidth] = useState('')
  const [refHeight, setRefHeight] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // Distinct from `error`: IMAGE_QUALITY_INSUFFICIENT is not "something went wrong", it's
  // "this photo can't be judged at all" -- rendered as its own panel below, never folded into
  // the generic error line, so it can never be mistaken for (or rendered as) a compliance
  // finding. See api/scans.py's quality-floor gate and client.js's structured `err.detail`.
  const [qualityIssue, setQualityIssue] = useState(null)
  const [elapsedMs, setElapsedMs] = useState(0)
  const timerRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading) {
      clearInterval(timerRef.current)
      return
    }
    setElapsedMs(0)
    const startedAt = Date.now()
    timerRef.current = setInterval(() => setElapsedMs(Date.now() - startedAt), 200)
    return () => clearInterval(timerRef.current)
  }, [loading])

  const stage = [...SCAN_STAGES].reverse().find((s) => elapsedMs >= s.afterMs) ?? SCAN_STAGES[0]

  function onFileChange(e) {
    const f = e.target.files[0]
    setFile(f)
    setPreview(f ? URL.createObjectURL(f) : null)
  }

  async function submit(e) {
    e.preventDefault()
    if (!file) return
    setLoading(true)
    setError('')
    setQualityIssue(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('product_name', productName || 'Unidentified product')
      if (category) fd.append('commodity_category', category)
      if (isImported) fd.append('is_imported', isImported === 'yes')
      if (isPerishable) fd.append('is_perishable_category', isPerishable === 'yes')
      if (refWidth) fd.append('reference_width_mm', refWidth)
      if (refHeight) fd.append('reference_height_mm', refHeight)
      const result = await api.createScan(fd)
      navigate(`/scans/${result.id}`)
    } catch (err) {
      if (err.detail?.code === 'IMAGE_QUALITY_INSUFFICIENT') {
        setQualityIssue(err.detail)
      } else {
        setError(err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2>Scan a package label</h2>
      <p className="muted">
        Upload a photo of the principal display panel. Declarations are checked against{' '}
        <a
          href="https://consumeraffairs.gov.in/pages/legal-metrology-act"
          target="_blank"
          rel="noreferrer"
        >
          Legal Metrology (Packaged Commodities) Rules, 2011
        </a>
        .
      </p>
      <form onSubmit={submit} className="scan-form">
        <label>Package photo</label>
        <input type="file" accept="image/*" onChange={onFileChange} required />
        {preview && (
          <img
            className="preview"
            src={preview}
            alt="Preview of the package photo selected for scanning"
          />
        )}

        <label>Product name</label>
        <input value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="e.g. Fresh Valley Snacks 200g" />

        <div className="form-row">
          <div>
            <label>Commodity category (known, if any)</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">Unknown / let system infer</option>
              <option value="solid">Solid (weight)</option>
              <option value="liquid">Liquid (volume)</option>
              <option value="count">Count-sold</option>
            </select>
          </div>
          <div>
            <label>Imported?</label>
            <select value={isImported} onChange={(e) => setIsImported(e.target.value)}>
              <option value="">Unknown</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
          <div>
            <label>Perishable category?</label>
            <select value={isPerishable} onChange={(e) => setIsPerishable(e.target.value)}>
              <option value="">Unknown</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
        </div>

        <details>
          <summary>Optional: Tier 2 font-size calibration</summary>
          <p className="muted small">
            Provide the package's real-world width/height in mm for a calibrated Rule 7 mm check.
            Without this, font-size findings are Tier 1 (relative) only — see methodology note in
            the report.
          </p>
          <div className="form-row">
            <div>
              <label>Reference width (mm)</label>
              <input type="number" value={refWidth} onChange={(e) => setRefWidth(e.target.value)} />
            </div>
            <div>
              <label>Reference height (mm)</label>
              <input type="number" value={refHeight} onChange={(e) => setRefHeight(e.target.value)} />
            </div>
          </div>
        </details>

        {loading && (
          <div className="scan-progress" role="status" aria-live="polite">
            <div className="scan-progress-bar">
              <div className="scan-progress-bar-fill" />
            </div>
            <p className="muted small">
              {stage.label} ({(elapsedMs / 1000).toFixed(0)}s — usually 5-15s, longer for a
              busy or multilingual label)
            </p>
          </div>
        )}

        {error && <div className="error">{error}</div>}

        {qualityIssue && (
          <div className="quality-floor-panel" role="alert">
            <h3>Photo couldn't be read reliably</h3>
            <p>{qualityIssue.message}</p>
            <p className="muted small">
              Measured: shorter side {qualityIssue.shorter_side_px}px, sharpness score{' '}
              {qualityIssue.laplacian_variance}. This is not a compliance finding — no check was
              run against this photo, and nothing was saved. Retake the photo and try again.
            </p>
          </div>
        )}

        <button type="submit" disabled={loading || !file}>
          {loading ? 'Scanning…' : 'Scan & check compliance'}
        </button>
      </form>
    </div>
  )
}
