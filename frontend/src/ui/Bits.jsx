/* Shared presentational primitives for the instrument shell.
 *
 * These exist so the status vocabulary is defined ONCE. Status colour is a
 * redundant channel in this design system (see tokens.css's dichromacy note:
 * the palette's hues collapse under protanopia/deuteranopia and no tuning
 * fixes it), so every status must also carry its glyph AND its text label.
 * Centralising that here is what stops a future screen from rendering a bare
 * coloured dot and quietly breaking WCAG 1.4.1 for this whole product.
 */

export const STATUS_META = {
  PASS: { glyph: '✓', label: 'Pass' },
  FAIL: { glyph: '✕', label: 'Fail' },
  NEEDS_VERIFICATION: { glyph: '!', label: 'Verify' },
  NOT_APPLICABLE: { glyph: '–', label: 'N/A' },
}

export function StatusChip({ status, size }) {
  const meta = STATUS_META[status] || STATUS_META.NOT_APPLICABLE
  return (
    <span className={`chip chip-${status}${size === 'lg' ? ' chip-lg' : ''}`}>
      <span className="chip-glyph" aria-hidden="true">{meta.glyph}</span>
      {meta.label}
    </span>
  )
}

export function PageHead({ eyebrow, title, sub, actions }) {
  return (
    <header className="page-head">
      <div className="page-head-row">
        <div>
          <div className="page-eyebrow">{eyebrow}</div>
          <h1 className="page-title">{title}</h1>
          {sub && <p className="page-sub">{sub}</p>}
        </div>
        {actions && <div className="page-head-actions">{actions}</div>}
      </div>
    </header>
  )
}

/* A score as a comparable quantity, not just a number. Bands mirror the
 * thresholds a reader intuitively applies, and the figure is always present --
 * the bar is an aid to scanning a column, never the only representation. */
export function ScoreCell({ score }) {
  if (score == null) return <span className="num muted">—</span>
  const band = score >= 80 ? 'high' : score >= 50 ? 'mid' : 'low'
  return (
    <div className="score-cell">
      <span className="score-track">
        <span className="score-fill" data-band={band} style={{ width: `${Math.max(2, score)}%` }} />
      </span>
      <span className="num">{score}%</span>
    </div>
  )
}

export function Empty({ title, hint, action }) {
  return (
    <div className="empty">
      <div className="empty-mark" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
          <path d="M4 12h16M12 4v16" />
        </svg>
      </div>
      <div className="empty-title">{title}</div>
      {hint && <p className="empty-hint">{hint}</p>}
      {action}
    </div>
  )
}

/* Fixed, unambiguous date form. toLocaleString() renders 01/09/2026 in one
 * locale and 09/01/2026 in another, and this is an evidentiary record where a
 * reader must not have to guess which. */
export function formatWhen(iso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getDate())} ${months[d.getMonth()]} ${d.getFullYear()}  ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
