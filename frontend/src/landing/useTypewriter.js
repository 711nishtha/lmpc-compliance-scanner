import { useEffect, useRef, useState } from 'react'

/**
 * Reveals `text` character-by-character after `startDelay` ms.
 *
 * @param {string} text        the full string to reveal
 * @param {number} speed       ms per character (default 38)
 * @param {number} startDelay  ms to wait before the first character (default 600)
 * @param {boolean} enabled    gate the effect (e.g. only start once in view)
 * @returns {{displayed: string, done: boolean}}
 *
 * Honours prefers-reduced-motion by revealing the whole string immediately — an animated
 * character crawl is exactly the kind of motion that setting exists to suppress.
 */
export function useTypewriter(text, speed = 38, startDelay = 600, enabled = true) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)
  const timers = useRef([])

  useEffect(() => {
    timers.current.forEach(clearTimeout)
    timers.current = []

    if (!enabled) {
      setDisplayed('')
      setDone(false)
      return undefined
    }

    const reduce =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    if (reduce) {
      setDisplayed(text)
      setDone(true)
      return undefined
    }

    setDisplayed('')
    setDone(false)

    // One timer per character keeps each reveal independent of render timing drift.
    for (let i = 1; i <= text.length; i++) {
      timers.current.push(
        setTimeout(() => setDisplayed(text.slice(0, i)), startDelay + i * speed)
      )
    }
    timers.current.push(
      setTimeout(() => setDone(true), startDelay + text.length * speed + 40)
    )

    return () => {
      timers.current.forEach(clearTimeout)
      timers.current = []
    }
  }, [text, speed, startDelay, enabled])

  return { displayed, done }
}
