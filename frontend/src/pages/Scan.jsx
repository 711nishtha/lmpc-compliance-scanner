import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

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
  const navigate = useNavigate()

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
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2>Scan a package label</h2>
      <p className="muted">
        Upload a photo of the principal display panel. Declarations are checked against{' '}
        <a href="/docs/LEGAL_REQUIREMENTS.md" target="_blank" rel="noreferrer">
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

        {error && <div className="error">{error}</div>}
        <button type="submit" disabled={loading || !file}>
          {loading ? 'Scanning…' : 'Scan & check compliance'}
        </button>
      </form>
    </div>
  )
}
