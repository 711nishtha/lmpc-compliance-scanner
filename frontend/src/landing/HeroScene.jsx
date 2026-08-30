/* 3D hero scene — LAZY-LOADED ONLY.
 *
 * This module (and only this module) pulls in three / @react-three/fiber / drei.
 * It must never be imported statically from App.jsx or any authenticated screen —
 * Landing.jsx wraps it in React.lazy so Vite emits it as a separate chunk and the
 * Scan/Report/Repository/Dashboard bundles stay Three-free.
 * Verified by scripts/check-bundle-isolation.mjs.
 *
 * Performance budget (must run on a demo laptop through a projector):
 *   - primitives only (box/cylinder/plane), no loaded models, no shadows
 *   - 2 lights total, no environment map
 *   - dpr capped at 1.5, frameloop pauses when tab is hidden
 *   - concept is on-theme: a package with a scan line sweeping it and rule-ID
 *     annotation chips popping in, mirroring the real bounding-box feature.
 */
import { Canvas, useFrame } from '@react-three/fiber'
import { Html, RoundedBox } from '@react-three/drei'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'

const BROWN = '#694A47'
const TEAL = '#96C1C5'
const CREAM = '#FFF0DE'

/* Theme-specific scene treatment — NOT a blind variable swap.
 *
 * The package itself stays light in both themes, because a real retail package IS
 * light; darkening it would misrepresent the subject. What changes is the STAGE:
 * the canvas background, the lighting balance and the status colours.
 *
 * In dark mode the ambient term drops and the key light rises, so the package
 * still has visible form and edge separation against a near-black ground instead
 * of flattening into a glowing slab. Status colours switch to the dark-mode
 * tokens measured in tokens.css. */
const SCENE = {
  light: {
    bg: '#FFF0DE',
    pass: '#2E5A3B',
    verify: '#8A6114',
    ambient: 1.25,
    key: 0.85,
    fill: 0.4,
  },
  dark: {
    bg: '#141821',
    pass: '#57C98C',
    verify: '#D9A93A',
    ambient: 0.62,
    key: 1.25,
    fill: 0.55,
  },
}

function useSceneTheme() {
  const read = () =>
    (typeof document !== 'undefined' &&
      document.documentElement.getAttribute('data-theme')) === 'dark'
      ? 'dark'
      : 'light'
  const [name, setName] = useState(read)
  useEffect(() => {
    const mo = new MutationObserver(() => setName(read()))
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => mo.disconnect()
  }, [])
  return SCENE[name]
}

/* Chips echo the real annotated-label output: rule id + verdict. */
// Anchored outside the box silhouette (half-width 0.95) so chips never sit on top of the
// artwork or each other, with a small connector dot on the face they refer to.
const CHIPS = [
  { id: 'R6-7', label: 'MRP', status: 'PASS', pos: [1.85, 0.74, 0.5], dot: [0.62, 0.34, 0.52], statusKey: 'pass' },
  { id: 'R6-4', label: 'NET QTY', status: 'PASS', pos: [-1.95, 0.06, 0.5], dot: [-0.5, 0.06, 0.52], statusKey: 'pass' },
  { id: 'R7-1', label: 'FONT', status: 'VERIFY', pos: [1.85, -0.72, 0.5], dot: [0.34, -0.54, 0.52], statusKey: 'verify' },
]

function Package({ scanY, theme }) {
  const group = useRef()
  useFrame((state) => {
    const t = state.clock.elapsedTime
    if (group.current) {
      group.current.rotation.y = Math.sin(t * 0.25) * 0.45
      group.current.position.y = Math.sin(t * 0.7) * 0.06
    }
  })

  // Printed "label lines" on the front face — cheap planes, no textures.
  const lines = useMemo(
    () => [
      { y: 0.66, w: 0.95, c: BROWN },
      { y: 0.34, w: 1.25, c: BROWN },
      { y: 0.06, w: 0.7, c: BROWN },
      { y: -0.22, w: 1.05, c: BROWN },
      { y: -0.54, w: 0.85, c: BROWN },
    ],
    []
  )

  return (
    <group ref={group}>
      <RoundedBox args={[1.9, 2.5, 1.0]} radius={0.07} smoothness={3} castShadow={false}>
        <meshStandardMaterial color={CREAM} roughness={0.5} metalness={0} />
      </RoundedBox>

      {/* brand band */}
      <mesh position={[0, 0.98, 0.505]}>
        <planeGeometry args={[1.9, 0.44]} />
        <meshStandardMaterial color={TEAL} roughness={0.6} />
      </mesh>

      {lines.map((l, i) => (
        <mesh key={i} position={[-(1.35 - l.w / 2) + 0.5, l.y, 0.506]}>
          <planeGeometry args={[l.w, 0.075]} />
          <meshStandardMaterial color={l.c} roughness={0.9} />
        </mesh>
      ))}

      {/* sweeping scan line */}
      <mesh position={[0, scanY, 0.53]}>
        <planeGeometry args={[2.05, 0.05]} />
        <meshBasicMaterial color={TEAL} transparent opacity={0.95} />
      </mesh>
      <mesh position={[0, scanY, 0.52]}>
        <planeGeometry args={[2.05, 0.42]} />
        <meshBasicMaterial color={TEAL} transparent opacity={0.16} />
      </mesh>

      {CHIPS.map((c) => (
        <group key={c.id}>
          <mesh position={c.dot}>
            <circleGeometry args={[0.055, 16]} />
            <meshBasicMaterial color={theme[c.statusKey]} />
          </mesh>
          <group position={c.pos}>
            <Html center distanceFactor={7.5} zIndexRange={[10, 0]}>
              <div className="scene-chip" style={{ '--chip': theme[c.statusKey] }}>
                <span className="scene-chip-id">{c.id}</span>
                <span className="scene-chip-label">{c.label}</span>
                <span className="scene-chip-status">{c.status}</span>
              </div>
            </Html>
          </group>
        </group>
      ))}
    </group>
  )
}

function Rig({ theme }) {
  const [scanY, setScanY] = useState(1.25)
  useFrame((state) => {
    const t = state.clock.elapsedTime
    // 4s sweep, top -> bottom, then snap back
    const phase = (t % 4) / 4
    setScanY(1.25 - phase * 2.5)
  })
  return <Package scanY={scanY} theme={theme} />
}

export default function HeroScene() {
  const t = useSceneTheme()
  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 0, 7.0], fov: 42 }}
      gl={{ antialias: true, powerPreference: 'high-performance' }}
      style={{ width: '100%', height: '100%' }}
    >
      <color attach="background" args={[t.bg]} />
      {/* 3 cheap lights, no shadow maps, no environment — keeps the frame budget low while
          stopping the cream box from reading as grey in the side planes. */}
      <ambientLight intensity={t.ambient} />
      <directionalLight position={[3, 4, 6]} intensity={t.key} color="#FFFFFF" />
      <directionalLight position={[-4, 1, 3]} intensity={t.fill} color={TEAL} />
      <Rig theme={t} />
    </Canvas>
  )
}
