/* Pre-login landing page.
 *
 * Bundle discipline: HeroScene (which owns every three/@react-three/fiber import)
 * is React.lazy'd, and GSAP is dynamically imported inside an effect. Neither is
 * reachable from the authenticated screens' import graph.
 * See scripts/check-bundle-isolation.mjs.
 */
import { Suspense, lazy, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import './landing.css'
import Hero from './Hero.jsx'

// Lazy for the same reason as the 3D scene: this section pulls in a 1.5MB mp4 and GSAP, neither
// of which belongs in the initial landing paint. Kept out of the app bundle too — verified by
// frontend/scripts/check-bundle-isolation.mjs.
const ScanShowcase = lazy(() => import('./ScanShowcase.jsx'))

const STEPS = [
  {
    k: '01',
    title: 'Scan the package',
    body: 'Upload a photo of the principal display panel. Preprocessing deskews, normalises contrast and upscales small print before OCR ever runs.',
  },
  {
    k: '02',
    title: 'Extract every declaration',
    body: 'Tesseract runs per-region with a dominant-script pre-pass, then regex/keyword extraction pulls MRP, net quantity, manufacturer, dates and consumer-care details — each one keeping its own bounding box and confidence.',
  },
  {
    k: '03',
    title: 'Check against the Rules',
    body: 'Fourteen itemised checks covering Rule 6 declarations, Rule 7 numeral height and Rule 8 placement — every verdict cited to the clause it came from.',
  },
  {
    k: '04',
    title: 'Issue the report',
    body: 'An annotated image plus a rule-cited PDF and an editable DOCX, filed into a searchable repository with a dashboard for enforcement officers.',
  },
]

const HONESTY = [
  ['Cited, never guessed', 'Every check names its clause. Anything unconfirmed against the Gazette text returns NEEDS VERIFICATION instead of a fabricated pass or fail.'],
  ['Tier 1 vs Tier 2', 'Font-size findings say plainly whether they are a relative signal or a calibrated millimetre measurement. They are never blended.'],
  ['Bad photo ≠ bad product', 'An unreadable image is flagged as an image problem, so an all-fail report is never mistaken for a non-compliant label.'],
]

export default function Landing() {
  const rootRef = useRef(null)

  useEffect(() => {
    let ctx
    let cancelled = false
    // GSAP is loaded on demand so it never enters the app bundle.
    ;(async () => {
      const [{ default: gsap }, { ScrollTrigger }] = await Promise.all([
        import('gsap'),
        import('gsap/ScrollTrigger'),
      ])
      if (cancelled) return
      gsap.registerPlugin(ScrollTrigger)

      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      if (reduce) return

      ctx = gsap.context(() => {
        gsap.utils.toArray('[data-reveal]').forEach((el) => {
          gsap.from(el, {
            opacity: 0,
            y: 16,
            duration: 0.45,
            ease: 'power1.out',
            scrollTrigger: { trigger: el, start: 'top 88%', toggleActions: 'play none none reverse' },
          })
        })
        gsap.utils.toArray('[data-reveal-stagger]').forEach((wrap) => {
          gsap.from(wrap.children, {
            opacity: 0,
            y: 18,
            duration: 0.4,
            ease: 'power1.out',
            stagger: 0.08,
            scrollTrigger: { trigger: wrap, start: 'top 85%', toggleActions: 'play none none reverse' },
          })
        })
      }, rootRef)
    })()

    return () => {
      cancelled = true
      if (ctx) ctx.revert()
    }
  }, [])

  return (
    <div className="landing" ref={rootRef}>
      <Hero />

      <Suspense fallback={<div className="showcase-fallback" />}>
        <ScanShowcase />
      </Suspense>

      <section className="landing-band" data-reveal>
        <h2>Manual inspection cannot keep up</h2>
        <p>
          Packaged commodities move through retail, supermarkets and e-commerce faster than
          enforcement teams can physically inspect them. Missing declarations, undersized MRP
          print and improperly placed net-quantity statements are common — and each one has to be
          found by eye, package by package.
        </p>
      </section>

      <section className="landing-steps" id="how">
        <h2 data-reveal>From photograph to filed report</h2>
        <div className="step-grid" data-reveal-stagger>
          {STEPS.map((s) => (
            <article className="step-card" key={s.k}>
              <span className="step-k">{s.k}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-band landing-band-alt" id="scripts" data-reveal>
        <h2>Reads the label as it is actually printed</h2>
        <p>
          Indian retail labels are rarely monolingual. The OCR layer runs English, Devanagari and
          Gujarati, picks the dominant script per line rather than forcing one model across the
          whole package, and normalises native-script numerals back to Arabic digits before any
          value is parsed.
        </p>
        <div className="script-row" data-reveal-stagger>
          <span className="script-chip">Net Wt. 200 g</span>
          <span className="script-chip">निर्माता: शिमला 171001</span>
          <span className="script-chip">ચોખ્ખો જથ્થો 1000 ml</span>
        </div>
      </section>

      <section className="landing-honesty">
        <h2 data-reveal>Built to be checkable</h2>
        <div className="honesty-grid" data-reveal-stagger>
          {HONESTY.map(([t, b]) => (
            <article className="honesty-card" key={t}>
              <h3>{t}</h3>
              <p>{b}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-final" data-reveal>
        <h2>Scan a label. Get the citation.</h2>
        <Link className="btn-primary btn-lg" to="/login">Launch the tool</Link>
        <p className="landing-foot">
          Decision support for enforcement officials — not a final legal determination.
        </p>
      </section>
    </div>
  )
}
