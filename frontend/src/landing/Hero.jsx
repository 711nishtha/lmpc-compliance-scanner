/* Landing hero — rebuilt from scratch as ONE coherent section.
 *
 * Structure (fixed nav + full-viewport stage, nothing else):
 *   [fixed nav]  wordmark left · links centre-right · CTA pill right
 *   [stage]      full-bleed video  ->  3-stop scrim  ->  centred content block
 *
 * Deliberately contains NO floating chips, glyphs or watermarks, and no 3D canvas.
 * The previous version layered all of those over each other and over the headline;
 * the content block is now the only thing above the scrim, so nothing can collide
 * with it. Any decorative layer comes back in a separate pass, positioned only where
 * it provably cannot overlap this block.
 *
 * Video: /demo/hero-ambient.* — the ambient loop from the visual reference bundle
 * (its public/hero-bg.webm), copied in at the user's explicit direction. Black-ground
 * abstract footage, which is what a hero background wants: white type sits on it
 * cleanly, so it needs almost none of the heavy darkening our own cream-UI recording
 * required. WebM/VP9 first with an H.264 fallback (Safari's WebM support is patchy).
 *
 * Our own scan-flow.mp4 keeps its dedicated home in the "See it scan" section below,
 * where literal product footage belongs and can be scrubbed.
 */
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import ThemeToggle from '../theme/ThemeToggle.jsx'
import './hero.css'

const NAV_ITEMS = [
  { label: 'How it works', href: '#how' },
  { label: 'See it scan', href: '#see-it-scan' },
  { label: 'Scripts read', href: '#scripts' },
]

export default function Hero() {
  const videoRef = useRef(null)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && setMenuOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    v.play?.().catch(() => {})
  }, [])

  return (
    <>
      <header className="hero-nav">
        <Link className="hero-wordmark" to="/">
          <span className="hero-mark" aria-hidden="true" />
          LMPC Compliance Scanner
        </Link>

        <nav className="hero-nav-links">
          {NAV_ITEMS.map((n) => (
            <a key={n.href} href={n.href}>{n.label}</a>
          ))}
        </nav>

        <div className="hero-nav-actions">
          <ThemeToggle />
          <button
            type="button"
            className="hero-burger"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            aria-controls="hero-mobile-nav"
            onClick={() => setMenuOpen((v) => !v)}
          >
            <span className="icon-menu" aria-hidden="true">&#9776;</span>
            <span className="icon-close" aria-hidden="true">&#10005;</span>
          </button>
          <Link className="hero-nav-cta" to="/login">Launch the tool</Link>
        </div>
      </header>

      <div
        className={`hero-overlay ${menuOpen ? 'open' : ''}`}
        aria-hidden="true"
        onClick={() => setMenuOpen(false)}
      />
      <div id="hero-mobile-nav" className={`hero-sheet ${menuOpen ? 'open' : ''}`}>
        <nav>
          {NAV_ITEMS.map((n) => (
            <a key={n.href} href={n.href} onClick={() => setMenuOpen(false)}>
              {n.label}<span aria-hidden="true">&rarr;</span>
            </a>
          ))}
          <Link to="/login" onClick={() => setMenuOpen(false)}>
            Launch the tool<span aria-hidden="true">&rarr;</span>
          </Link>
        </nav>
      </div>

      <section className="hero-stage">
        <video
          ref={videoRef}
          className="hero-video"
          muted
          loop
          playsInline
          preload="auto"
          aria-hidden="true"
          tabIndex={-1}
        >
          <source src="/demo/hero-ambient.webm" type="video/webm" />
          <source src="/demo/hero-ambient.mp4" type="video/mp4" />
        </video>
        <div className="hero-scrim" aria-hidden="true" />

        <div className="hero-content">
          <p className="hero-eyebrow hero-reveal hero-d1">
            SIH26034 &middot; Department of Consumer Affairs
          </p>
          <h1 className="hero-title hero-reveal hero-d1">
            Legal Metrology compliance,
            <br />
            <span className="hero-title-soft">checked from a photograph.</span>
          </h1>
          <p className="hero-subhead hero-reveal hero-d2">
            Upload a package label and get an itemised, clause-cited report under the Legal
            Metrology (Packaged Commodities) Rules, 2011.
          </p>
          <div className="hero-actions hero-reveal hero-d3">
            <Link className="hero-btn hero-btn-primary" to="/login">Launch the tool</Link>
            <a className="hero-btn hero-btn-ghost" href="#see-it-scan">See it scan</a>
          </div>
        </div>
      </section>
    </>
  )
}
