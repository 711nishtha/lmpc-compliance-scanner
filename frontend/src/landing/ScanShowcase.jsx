/* "See it scan" — sits directly BELOW the 3D hero, never instead of it.
 *
 * This whole module (including the mp4 reference) is lazy-loaded by Landing.jsx for the same
 * reason Three.js is: a 1.5MB compliance-scan video has no business in the initial landing paint.
 * GSAP is imported dynamically here too, matching the pattern already used in Landing.jsx —
 * no second animation library is introduced.
 *
 * The footage is REAL: recorded by frontend/qa/20_record_demo.js driving the live app through
 * demo label 01 (fully compliant) and demo label 12 (placement violation), back to back.
 */
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import MouseScrubVideo from './MouseScrubVideo.jsx'
import { useTypewriter } from './useTypewriter.js'

const HEADLINE = 'One photograph in. Every clause accounted for.'

// Wording describes what this product actually does — each pill maps to a real screen/feature.
const PILLS = [
  { label: 'Try a live scan', to: '/login' },
  { label: 'Read the compliance report', to: '/login' },
  { label: 'See the rule citations', to: '/login' },
]

export default function ScanShowcase() {
  const rootRef = useRef(null)
  const pillsRef = useRef(null)
  const [inView, setInView] = useState(false)

  // Typewriter only starts once the section is actually on screen — otherwise it has already
  // finished by the time anyone scrolls to it.
  useEffect(() => {
    const el = rootRef.current
    if (!el) return undefined
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          io.disconnect()
        }
      },
      { threshold: 0.25 }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  const { displayed, done } = useTypewriter(HEADLINE, 38, 600, inView)

  // Staggered pill reveal — same GSAP ScrollTrigger pattern as the rest of the landing page.
  useEffect(() => {
    let ctx
    let cancelled = false
    ;(async () => {
      const [{ default: gsap }, { ScrollTrigger }] = await Promise.all([
        import('gsap'),
        import('gsap/ScrollTrigger'),
      ])
      if (cancelled || !pillsRef.current) return
      gsap.registerPlugin(ScrollTrigger)
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

      ctx = gsap.context(() => {
        gsap.from(pillsRef.current.children, {
          opacity: 0,
          y: 14,
          duration: 0.4,
          ease: 'power1.out',
          stagger: 0.09,
          scrollTrigger: {
            trigger: pillsRef.current,
            start: 'top 88%',
            toggleActions: 'play none none reverse',
          },
        })
      }, pillsRef)
    })()
    return () => {
      cancelled = true
      if (ctx) ctx.revert()
    }
  }, [])

  return (
    <section className="scan-showcase" ref={rootRef} id="see-it-scan">
      <div className="scan-showcase-head">
        <p className="landing-eyebrow">Real footage · not a mockup</p>
        <h2 className="typewriter-line">
          {/* The full headline is always in the accessible tree; the animated copy is
              aria-hidden so screen readers don't hear it rebuild character by character. */}
          <span className="sr-only">{HEADLINE}</span>
          <span aria-hidden="true">
            {displayed}
            {!done && <span className="typewriter-cursor" />}
          </span>
        </h2>
        <p className="scan-showcase-lede">
          Recorded straight from the running tool: a compliant label, then one with its MRP
          printed away from the principal display panel. Same pipeline, same citations, no edits.
        </p>
      </div>

      <MouseScrubVideo
        src="/demo/scan-flow.mp4"
        className="scan-showcase-video"
        label="Screen recording of two package labels being scanned and their compliance reports generated"
      />

      <div className="scan-pills" ref={pillsRef}>
        {PILLS.map((p) => (
          <Link key={p.label} className="scan-pill" to={p.to}>
            {p.label}
          </Link>
        ))}
      </div>
    </section>
  )
}
