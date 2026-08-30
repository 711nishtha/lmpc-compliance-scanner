# Design System — LMPC Compliance Scanner

Single source of truth: **`frontend/src/tokens.css`**. Every component references tokens; no
component hardcodes a hex value. A palette change should be an edit to that one file — plus the
two Python mirrors called out below, which is the one unavoidable exception.

## 1. Palette

Supplied brand palette ("American Vintage"):

| Token | Hex | Role |
|---|---|---|
| `--color-brand-brown` | `#694A47` | Primary action, nav, headings, body text base |
| `--color-brand-teal` | `#96C1C5` | **Accent surface only** — fills, borders, hover washes |
| `--color-brand-cream` | `#FFF0DE` | Page background |

### Why teal is not the primary color

The obvious reading of this palette is "teal = primary, brown = text." Measured against WCAG 2.1
that is unusable:

| Combination | Ratio | Verdict |
|---|---|---|
| white text on teal | 1.96:1 | ✗ fails (needs 4.5:1) |
| teal text on cream | 1.75:1 | ✗ fails |
| teal text on white | 1.96:1 | ✗ fails |
| **white text on brown** | **7.86:1** | ✓ passes comfortably |
| brown text on teal | 4.02:1 | ⚠ large text only (≥18.66px bold / ≥24px) |

So **brown carries every text-bearing and interactive role**; teal is a surface/edge accent. Do not
"fix" this later by making buttons teal — it silently breaks legibility on a projector.

## 2. Status colors — derived, not supplied

The palette contains no success/fail/warning hues. These were derived to stay vintage-consistent
and then measured:

| Status | Token | Hex | White text on fill | As text on cream |
|---|---|---|---|---|
| PASS | `--color-status-pass` | `#2E5A3B` | 7.95:1 ✓ | 7.11:1 ✓ |
| FAIL | `--color-status-fail` | `#A63A2B` | 6.44:1 ✓ | 5.76:1 ✓ |
| NEEDS_VERIFICATION | `--color-status-verify` | `#8A6114` | 5.53:1 ✓ | 4.94:1 ✓ |
| NOT_APPLICABLE | `--color-status-na` | `#6B605A` | 6.09:1 ✓ | 5.45:1 ✓ |

### The colorblind finding (important, and not fixable by better colors)

Dichromat simulation (protan/deutan/tritan) of the status colors returns **1.15–1.51 separation for
FAIL vs NEEDS_VERIFICATION** — effectively indistinguishable. Three luminance-staggered candidate
sets were tested; staggering fixed PASS-vs-others (up to 3.3 separation) but never fixed
red-vs-amber, and pushing them further apart broke the 4.5:1 white-text requirement instead.

This is inherent to red vs amber, not a bad palette choice. **Conclusion: color is a redundant
channel here, never the sole carrier of meaning** (WCAG 1.4.1). Every status therefore ships:

1. its **text label** (`PASS` / `FAIL` / `NEEDS_VERIFICATION`) — already present in table, badge, PDF, DOCX;
2. a **distinct glyph** — `✓` / `✕` / `!` / `–` via `.badge::before` in `index.css`;
3. color, as reinforcement only.

Do not remove (1) or (2) to tidy up the UI. They are the accessibility mechanism.

## 3. The Python mirrors (only place tokens are duplicated)

Status colors are consumed by two Python modules that cannot read CSS:

| File | Constant | Format |
|---|---|---|
| `backend/app/reports/annotate.py` | `STATUS_BGR` | OpenCV **B,G,R** tuples |
| `backend/app/reports/pdf.py` | `STATUS_COLORS` | ReportLab `HexColor` |

Changing `--color-status-*` **requires** updating both, or the annotated label image and the PDF
will silently disagree with the on-screen legend. Both files carry a comment pointing back here.

## 4. Typography

From `ui-ux-pro-max` (pairing: *SaaS Mobile Boutique*) — chosen over the more literal "Retro
Vintage" pairing because Abril Fatface is a decorative display face unsuited to a dense enforcement
table.

| Token | Family | Used for |
|---|---|---|
| `--font-display` | Calistoga | Headings, landing hero, stat values |
| `--font-body` | Inter | All body text, forms, buttons |
| `--font-mono` | JetBrains Mono | Rule IDs, badges, data labels, legends |

Mono on rule IDs and extracted values is functional, not decorative — it makes `R6-1` vs `R8-1`
scannable in a dense table.

## 5. Rules for contributors

- Never write a raw hex in a component. Add a token.
- Never use teal for text or for a white-text button.
- Never let color be the only signal for a status.
- Body text minimum 16px (`--text-base`); mono labels may go to 12px (`--text-xs`).
- Interactive targets ≥44px tall.
- Motion 150–300ms, and `prefers-reduced-motion` collapses all durations to 1ms (already wired in
  `tokens.css`).

## 6. Verification

Contrast and dichromat figures above were produced by a real script, not estimated by eye —
see the working scripts under the session scratchpad (`contrast.py`, `contrast2.py`,
`contrast_final.py`). Re-run them if the palette changes.
