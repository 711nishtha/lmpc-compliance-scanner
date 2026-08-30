import { useEffect, useRef, useState } from 'react'

/**
 * Video whose playhead is driven by horizontal mouse movement.
 *
 *   currentTime += (mouseDeltaX / innerWidth) * SCRUB_GAIN * duration,  clamped to [0, duration]
 *
 * Seek discipline: setting `currentTime` on every mousemove floods the decoder and produces a
 * stuttering, laggy scrub. Instead we keep a single pending target and only issue the next seek
 * once the previous one has fired `seeked` — so at most one seek is ever in flight.
 *
 * Touch/coarse-pointer devices emit no mousemove. Rather than shipping a video frozen on frame 0
 * (a dead black box), those devices get autoplay+loop. This mechanic simply has no mobile
 * equivalent, so the fallback is a different experience by design, not a broken one.
 *
 * prefers-reduced-motion also gets the static-poster treatment rather than looping motion.
 */

const SCRUB_GAIN = 0.8

// Frame 0 of the recording is the empty page before the app has painted, so a video parked at
// currentTime=0 renders as a blank white box and the section reads as broken before the user
// scrubs. Open on a frame that actually shows a rendered compliance report instead.
const REST_FRACTION = 0.34

export default function MouseScrubVideo({ src, poster, className = '', label }) {
  const videoRef = useRef(null)
  const targetTime = useRef(0)
  const seeking = useRef(false)
  const lastX = useRef(null)
  const [mode, setMode] = useState('scrub') // 'scrub' | 'autoplay' | 'static'
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return undefined

    const coarse = window.matchMedia?.('(pointer: coarse)').matches
    const noHover = window.matchMedia?.('(hover: none)').matches
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    if (reduce) {
      setMode('static')
      return undefined
    }
    if (coarse || noHover) {
      setMode('autoplay')
      video.loop = true
      // play() can reject (autoplay policy); a muted inline video is normally allowed, but
      // swallow the rejection rather than throwing an unhandled promise.
      video.play().catch(() => {})
      return undefined
    }

    setMode('scrub')

    const onSeeked = () => {
      const v = videoRef.current
      if (!v) return
      // If the target moved while this seek was in flight, chase it now.
      if (Math.abs(v.currentTime - targetTime.current) > 0.01) {
        v.currentTime = targetTime.current
      } else {
        seeking.current = false
      }
    }

    const onMouseMove = (e) => {
      const v = videoRef.current
      if (!v || !v.duration || Number.isNaN(v.duration)) return
      if (lastX.current === null) {
        lastX.current = e.clientX
        return
      }
      const dx = e.clientX - lastX.current
      lastX.current = e.clientX

      const next = targetTime.current + (dx / window.innerWidth) * SCRUB_GAIN * v.duration
      targetTime.current = Math.min(Math.max(next, 0), v.duration)

      if (!seeking.current) {
        seeking.current = true
        v.currentTime = targetTime.current
      }
    }

    video.addEventListener('seeked', onSeeked)
    window.addEventListener('mousemove', onMouseMove, { passive: true })
    return () => {
      video.removeEventListener('seeked', onSeeked)
      window.removeEventListener('mousemove', onMouseMove)
    }
  }, [])

  return (
    <div className={`scrub-video-wrap ${className}`}>
      <video
        ref={videoRef}
        src={src}
        poster={poster}
        muted
        playsInline
        preload="auto"
        aria-label={label}
        className="scrub-video"
        onLoadedMetadata={(e) => {
          setReady(true)
          const v = e.currentTarget
          if (v.duration && !Number.isNaN(v.duration)) {
            const rest = v.duration * REST_FRACTION
            targetTime.current = rest
            // Only park the playhead for the scrub/static modes; autoplay mode should run
            // from the top so the mobile fallback tells the whole story.
            if (!v.loop) v.currentTime = rest
          }
        }}
      />
      {mode === 'scrub' && (
        <p className="scrub-hint" aria-hidden="true">
          {ready ? 'Move your mouse to scrub through a real scan' : 'Loading real scan footage…'}
        </p>
      )}
      {mode === 'static' && (
        <p className="scrub-hint" aria-hidden="true">
          Motion reduced — showing a still frame of a real scan
        </p>
      )}
    </div>
  )
}
