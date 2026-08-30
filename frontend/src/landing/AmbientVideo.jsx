/* Ambient texture behind the hero — OUR OWN footage, blurred.
 *
 * Reuses /demo/scan-flow.mp4: the real label-01/label-12 scan recorded from this app.
 * The reference site's background video is a pre-rendered asset hosted under another
 * user's account, so none of it is used here — only the treatment (full-bleed cover +
 * a three-stop scrim) is reimplemented.
 *
 * At rest this is atmosphere, not content: it is heavily blurred and desaturated so it
 * never competes with the 3D centrepiece or the headline. The SHARP, scrubbable version
 * of this same footage lives in the "See it scan" section further down the page.
 *
 * Skipped entirely under prefers-reduced-motion and on save-data connections.
 */
import { useEffect, useRef, useState } from 'react'

export default function AmbientVideo() {
  const ref = useRef(null)
  const [enabled, setEnabled] = useState(false)

  useEffect(() => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const saveData = navigator.connection?.saveData
    if (reduce || saveData) return
    setEnabled(true)
  }, [])

  useEffect(() => {
    if (!enabled) return
    const v = ref.current
    if (v) v.play?.().catch(() => {})
  }, [enabled])

  return (
    <div className="ambient-layer" aria-hidden="true">
      {enabled && (
        <video
          ref={ref}
          className="ambient-video"
          src="/demo/scan-flow.mp4"
          muted
          loop
          playsInline
          preload="metadata"
          tabIndex={-1}
        />
      )}
      {/* Scrim: opacity stops adapted from the reference (60% top / 20% mid / 70% bottom),
          driven by per-theme tokens so light mode isn't just the dark scrim reused. */}
      <div className="ambient-scrim" />
    </div>
  )
}
