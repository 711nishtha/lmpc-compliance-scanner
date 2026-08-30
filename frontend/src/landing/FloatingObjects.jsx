/* Thematic ambient objects — atmosphere with meaning, not decorative soup.
 *
 * Deliberately a RESTRAINED SUBSET of the options considered: real rule-citation chips
 * and real multilingual glyphs. Skipped: magnifier, scan-line motif and stamp seal —
 * with the 3D scene, the ambient video and the scan-line sweep already moving, adding
 * those tipped it from "homely" into cluttered. Pulling back was the better call.
 *
 * Implementation note: these are DOM elements animated with pure CSS transforms, not
 * extra R3F meshes. Transform/opacity animation runs on the compositor, so this costs
 * the 3D scene's frame budget essentially nothing — measured, see the QA output.
 *
 * The chips reuse the real .badge visual language from the Scan/Report UI (same shape,
 * same status colour tokens, same glyphs) so they read as "this is what the tool emits".
 */

// Real citations this tool actually produces, with their real statuses.
const CHIPS = [
  { id: 'r6-7',  text: 'R6-7 MRP',    status: 'pass',   glyph: '\u2713' },
  { id: 'r8-1',  text: 'R8-1 PLACEMENT', status: 'fail', glyph: '\u2715' },
  { id: 'r6-2',  text: 'R6-2 ORIGIN', status: 'verify', glyph: '!' },
  { id: 'r7-1',  text: 'R7-1 FONT',   status: 'pass',   glyph: '\u2713' },
]

// Real scripts the OCR pipeline supports (eng/hin/guj), not generic decoration.
const GLYPHS = [
  { id: 'g-en', text: 'MRP' },
  { id: 'g-hi', text: '\u0928\u093F\u0930\u094D\u092E\u093E\u0923' }, // निर्माण — "manufacture"
  { id: 'g-gu', text: '\u0AB5\u0A9C\u0AA8' },                          // વજન — "weight"
]

export default function FloatingObjects() {
  return (
    <div className="floaters" aria-hidden="true">
      {CHIPS.map((c, i) => (
        <span key={c.id} className={`floater floater-chip status-${c.status} f${i + 1}`}>
          <span className="floater-glyph">{c.glyph}</span>
          {c.text}
        </span>
      ))}
      {GLYPHS.map((g, i) => (
        <span key={g.id} className={`floater floater-glyph-word g${i + 1}`}>
          {g.text}
        </span>
      ))}
    </div>
  )
}
