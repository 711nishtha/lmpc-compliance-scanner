/* Proves the 3D landing page's dependencies do NOT leak into the authenticated app bundle.
 *
 * Requirement: the pre-login landing page may use three/@react-three/fiber/drei/gsap, but the
 * Scan / Report / Repository / Dashboard screens must stay on plain token-based styling and must
 * never pay for that bundle. "It's lazy-loaded" is an assumption until the build output says so —
 * this checks the real emitted chunks.
 *
 * Run:  npm run build && node scripts/check-bundle-isolation.mjs
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const ASSETS = join(process.cwd(), 'dist', 'assets')

// Signatures that only appear if the heavy libs were actually bundled into a chunk.
const HEAVY = [
  { name: 'three',   probe: /THREE\.WebGLRenderer|WebGLRenderer:|three\.module/i },
  { name: 'r3f/drei', probe: /@react-three|react-three-fiber|useFrame/i },
  { name: 'gsap',    probe: /gsap|ScrollTrigger/i },
  // The "See it scan" showcase: its mp4 reference and scrub logic must also stay out of the
  // authenticated app bundle.
  { name: 'scan-video', probe: /scan-flow\.mp4|MouseScrubVideo|scrub-video/i },
]

// A chunk is "app-critical" if it contains code from the authenticated screens.
const APP_MARKERS = [
  'Itemized rule-cited results', // ScanDetail
  'Scan a package label',        // Scan
  'Scanned products',            // Repository
  'Enforcement dashboard',       // Dashboard
]

let files
try {
  files = readdirSync(ASSETS).filter((f) => f.endsWith('.js'))
} catch {
  console.error('FAIL: dist/assets not found — run `npm run build` first.')
  process.exit(1)
}

const chunks = files.map((f) => {
  const p = join(ASSETS, f)
  const src = readFileSync(p, 'utf8')
  return {
    file: f,
    kb: +(statSync(p).size / 1024).toFixed(1),
    src,
    hasApp: APP_MARKERS.filter((m) => src.includes(m)),
    heavy: HEAVY.filter((h) => h.probe.test(src)).map((h) => h.name),
  }
})

console.log('=== emitted JS chunks ===')
for (const c of chunks) {
  console.log(
    `  ${c.file}  ${String(c.kb).padStart(8)} KB  ` +
      `app-screens:[${c.hasApp.length ? c.hasApp.length : '-'}]  heavy:[${c.heavy.join(',') || '-'}]`
  )
}

const violations = chunks.filter((c) => c.hasApp.length > 0 && c.heavy.length > 0)

console.log('\n=== verdict ===')
if (violations.length) {
  console.error('FAIL: heavy 3D/animation libs are bundled together with authenticated app screens:')
  for (const v of violations) {
    console.error(`  ${v.file}: screens=${v.hasApp.join('|')} heavy=${v.heavy.join(',')}`)
  }
  process.exit(1)
}

const heavyChunks = chunks.filter((c) => c.heavy.length > 0)
const appChunks = chunks.filter((c) => c.hasApp.length > 0)
console.log(`  app-screen chunks : ${appChunks.map((c) => `${c.file} (${c.kb}KB)`).join(', ') || 'none found'}`)
console.log(`  heavy-lib chunks  : ${heavyChunks.map((c) => `${c.file} (${c.kb}KB)`).join(', ') || 'none'}`)
console.log('  PASS: no chunk contains both an authenticated screen and a 3D/animation library.')
