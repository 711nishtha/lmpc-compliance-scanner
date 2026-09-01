import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { PageHead } from '../ui/Bits.jsx'

// A scan is one synchronous request -- the backend doesn't stream real progress events, so a
// bar claiming an exact percentage would be exactly the kind of fabricated certainty this
// project refuses to produce elsewhere. Instead: an indeterminate sweep (genuinely "still
// working", not "N% done"), paired with captions timed off what the pipeline actually does and
// how long each stage really takes on a real photo. Measured this build cycle: the dual-pass
// OCR ensemble is ~18s on a real packet photo and the vision pass adds 4-6s on top.
// Purely informational texture, not a claim about progress -- if this drifts from reality,
// update the thresholds, not the disclaimer.
const SCAN_STAGES = [
  { afterMs: 0, label: 'Uploading photograph' },
  { afterMs: 900, label: 'Checking image quality' },
  { afterMs: 2200, label: 'Reading the label (OCR, two passes)' },
  { afterMs: 9000, label: 'Second reading by the vision model' },
  { afterMs: 14000, label: 'Extracting declarations' },
  { afterMs: 17000, label: 'Checking against Rules 6, 7 & 8' },
  { afterMs: 24000, label: 'Still working — busy or multilingual labels take longer' },
]

export default function Scan() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [dragging, setDragging] = useState(false)
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
  const inputRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading) { clearInterval(timerRef.current); return }
    setElapsedMs(0)
    const startedAt = Date.now()
    timerRef.current = setInterval(() => setElapsedMs(Date.now() - startedAt), 200)
    return () => clearInterval(timerRef.current)
  }, [loading])

  // Revoke the previous object URL whenever it is replaced, and on unmount. Without this every
  // re-pick leaks a blob for the lifetime of the tab.
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const stage = [...SCAN_STAGES].reverse().find((s) => elapsedMs >= s.afterMs) ?? SCAN_STAGES[0]
  const stageIndex = SCAN_STAGES.indexOf(stage)

  function accept(f) {
    if (!f || !f.type.startsWith('image/')) return
    setFile(f)
    setPreview((prev) => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(f) })
    setQualityIssue(null)
    setError('')
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
      if (err.detail?.code === 'IMAGE_QUALITY_INSUFFICIENT') setQualityIssue(err.detail)
      else setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHead
        eyebrow="Field inspection"
        title="Scan a package label"
        sub="Photograph the principal display panel. Every declaration found is checked against the Legal Metrology (Packaged Commodities) Rules, 2011, and reported with the clause that requires it."
      />

      <form onSubmit={submit} className="scan-layout">
        {/* ---- Left: the capture bay ---------------------------------------- */}
        <section className="panel scan-bay">
          <div className="panel-head">
            <h2 className="panel-title">Specimen</h2>
            <span className="panel-note">{file ? file.name : 'no photograph loaded'}</span>
          </div>

          <div className="bay-frame bracket">
          <div
            className={`dropzone${dragging ? ' is-drag' : ''}${preview ? ' has-file' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); accept(e.dataTransfer.files[0]) }}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
            aria-label="Choose or drop a photograph of the package label"
          >
            {preview ? (
              <>
                <img className="dropzone-img" src={preview} alt="Selected package label" />
                {loading && <span className="scanline" aria-hidden="true" />}
              </>
            ) : (
              <div className="dropzone-empty">
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     strokeWidth="1.2" strokeLinecap="round" aria-hidden="true">
                  <path d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3" />
                  <circle cx="12" cy="12" r="3.2" />
                </svg>
                <p className="dropzone-title">Drop a label photograph</p>
                <p className="dropzone-hint">or click to browse · JPEG, PNG, WebP · up to 12 MB</p>
              </div>
            )}
            <input
              ref={inputRef} className="visually-hidden" type="file" accept="image/*"
              onChange={(e) => accept(e.target.files[0])}
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          </div>

          {preview && !loading && (
            <div className="bay-actions">
              <button type="button" className="btn-inst btn-ghost btn-small"
                      onClick={() => inputRef.current?.click()}>
                Replace photograph
              </button>
            </div>
          )}

          {loading && (
            <div className="scan-progress" role="status" aria-live="polite">
              <ol className="stage-list">
                {SCAN_STAGES.slice(0, 6).map((s, i) => (
                  <li key={s.label}
                      className={i < stageIndex ? 'is-done' : i === stageIndex ? 'is-now' : ''}>
                    <span className="stage-dot" aria-hidden="true" />
                    {s.label}
                  </li>
                ))}
              </ol>
              <p className="stage-meta">
                {(elapsedMs / 1000).toFixed(0)}s elapsed · typically 20–30s, longer for a busy or
                multilingual label
              </p>
            </div>
          )}
        </section>

        {/* ---- Right: the docket -------------------------------------------- */}
        <section className="scan-side">
          <div className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Docket</h2>
              <span className="panel-note">optional context</span>
            </div>
            <div className="panel-pad scan-fields">
              <div className="field">
                <label className="field-label" htmlFor="pn">Product name</label>
                <input id="pn" className="inst-input" value={productName}
                       placeholder="e.g. Fresh Valley Snacks 200g"
                       onChange={(e) => setProductName(e.target.value)} />
              </div>

              <div className="field">
                <label className="field-label" htmlFor="cc">Commodity category</label>
                <select id="cc" className="inst-select" value={category}
                        onChange={(e) => setCategory(e.target.value)}>
                  <option value="">Unknown — let the system infer</option>
                  <option value="solid">Solid (weight)</option>
                  <option value="liquid">Liquid (volume)</option>
                  <option value="count">Count-sold</option>
                </select>
              </div>

              <div className="field-pair">
                <div className="field">
                  <label className="field-label" htmlFor="im">Imported</label>
                  <select id="im" className="inst-select" value={isImported}
                          onChange={(e) => setIsImported(e.target.value)}>
                    <option value="">Unknown</option>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="pe">Perishable</label>
                  <select id="pe" className="inst-select" value={isPerishable}
                          onChange={(e) => setIsPerishable(e.target.value)}>
                    <option value="">Unknown</option>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Calibration</h2>
              <span className="panel-note">tier 2</span>
            </div>
            <div className="panel-pad scan-fields">
              <p className="calib-note">
                Give the package's real-world dimensions and Rule 7 font-size findings become an
                actual millimetre measurement against Table&nbsp;I. Without them, font size is
                reported as a relative signal only.
              </p>
              <div className="field-pair">
                <div className="field">
                  <label className="field-label" htmlFor="rw">Width (mm)</label>
                  <input id="rw" className="inst-input" type="number" min="1" value={refWidth}
                         onChange={(e) => setRefWidth(e.target.value)} placeholder="—" />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="rh">Height (mm)</label>
                  <input id="rh" className="inst-input" type="number" min="1" value={refHeight}
                         onChange={(e) => setRefHeight(e.target.value)} placeholder="—" />
                </div>
              </div>
            </div>
          </div>

          {error && <div className="auth-error">{error}</div>}

          {qualityIssue && (
            <div className="quality-panel" role="alert">
              <div className="quality-head">Photograph could not be read</div>
              <p>{qualityIssue.message}</p>
              <p className="quality-meta">
                Measured: shorter side {qualityIssue.shorter_side_px}px · sharpness{' '}
                {qualityIssue.laplacian_variance}. This is not a compliance finding — no check ran
                against this photo and nothing was saved.
              </p>
            </div>
          )}

          <button className="btn-inst scan-submit" type="submit" disabled={loading || !file}>
            {loading ? 'Scanning…' : 'Run compliance check'}
          </button>
          <p className="scan-foot">
            Findings are machine determinations under the{' '}
            <a href="https://consumeraffairs.gov.in/pages/legal-metrology-act"
               target="_blank" rel="noreferrer">Rules of 2011</a>. Items the system cannot decide
            are reported as needing verification, never guessed.
          </p>
        </section>
      </form>
    </>
  )
}
