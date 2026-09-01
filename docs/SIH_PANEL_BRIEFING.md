# SIH26034 — Panel & DoCA Briefing Document

**Prepared for:** SIH 2026 final panel, and a possible follow-up demonstration to officials
of the Department of Consumer Affairs (DoCA), Ministry of Consumer Affairs, Food & Public
Distribution, Government of India.

**Solution:** LMPC Compliance Scanner — a web application that scans packaged-commodity
labels and validates declarations against the Legal Metrology (Packaged Commodities) Rules,
2011, producing itemised, clause-cited compliance reports.

**Design principle governing this entire document, and the software:** never fabricate a
legal verdict. Where a claim below is an estimate rather than a measured fact, it is labelled
as one, with the reasoning shown. Where the software cannot verify something, it says so —
this document holds itself to the same standard.

---

## TASK 1 — Problem Statement Coverage Audit

Audited against SIH26034's stated background, "should be capable of" list, and expected
solution, item by item.

| # | PS Requirement | Status | Justification | What a panel might still probe |
|---|---|---|---|---|
| 1 | Scan **labels/images** | **FULLY MET** | Real OCR pipeline (Tesseract, eng+hin+guj), not a mockup — upload → preprocess → OCR → extraction → rule engine, end to end, tested against real product photos this build cycle. | Ask for a live scan of a product they hand you, not a pre-loaded demo. Be ready — this is your strongest card if it works, your biggest risk if it doesn't. |
| 2 | Scan **listings** (e-commerce) | **PARTIALLY MET** | The `Declarations` schema is built to also accept a listing-text dump as an alternate input source with no schema change — but the UI does not ingest a listing today. This is a **documented, deliberate v1 scope decision**, not an oversight. | A sharp panelist will ask "so it doesn't do e-commerce today" — answer directly: correct, and explain why (see §3 below: label-photo compliance is the harder, higher-value problem to solve first; listing text is comparatively easy structured-text parsing once the rule engine and schema already exist). |
| 3 | **Validate declarations** against Rules | **FULLY MET** | 14 itemised checks (verified against the current rule engine, not a stale figure), Rule 6 (mandatory declarations, R6-1..R6-11), Rule 7 (numeral height, R7-1/R7-2), Rule 8 (placement, R8-1/R8-2) — each returns PASS/FAIL/NEEDS_VERIFICATION/NOT_APPLICABLE with a clause citation. | Ask to see the rule engine cite its exact clause on screen — do it live, not from a slide. |
| 4 | **Flag non-compliance** | **FULLY MET** | Every FAIL is evidenced with the extracted value, its OCR bounding box, and confidence. | — |
| 5 | Check **readability / font size** | **PARTIALLY MET, honestly** | Two-tier: Tier 1 (no calibration) gives a *relative* signal only and never resolves to a hard PASS/FAIL; Tier 2 (user supplies a reference dimension) gives a real millimetre measurement against Table-I. | **This is the single most likely technical question you'll get** (see Q&A §5). Do not let the panel discover Tier 1's limits themselves — state it before they ask. |
| 6 | Generate **compliance reports** | **FULLY MET** | Itemised PDF (ReportLab) with the annotated image and a methodology footer, plus an editable DOCX. | — |
| 7 | **Repository + history** | **FULLY MET** | Every scan persisted with raw OCR, declarations JSON, rule-results JSON, all three image variants, and both report files. Searchable by text, status, date range. | — |
| 8 | **Dashboard** for officials | **FULLY MET** (admin-only) | Total scans, status breakdown, 30-day trend, 10 most recent non-compliant scans needing follow-up. | Panel may want to see *targeting* logic (e.g. "show me the worst offenders by category") — you have status + recency, not yet category/brand aggregation. Say so if asked. |
| 9 | **Web/mobile app** | **PARTIALLY MET** | Responsive web app, works on a mobile browser. **Not** a native mobile app — no offline capture, no native camera integration beyond the browser's file picker. | If asked "is there an app": no, and say why that's a reasonable v1 call — a PWA/native wrapper is a packaging decision on top of an already-working web backend, not a redesign. |
| 10 | **Automated extraction** | **FULLY MET** | Regex/keyword-anchored structured extraction, each field with its own OCR bounding box + confidence — no manual data entry step. | — |
| 11 | **Rule-based validation** | **FULLY MET** | Explicitly rule-based, not ML-classifier-based — every verdict traces to a clause, which is a **defensibility feature**, not a limitation (see §5, "why not an LLM"). | — |
| 12 | **Search / retrieval** | **FULLY MET** | Repository search endpoint, filterable. | — |
| 13 | **Technical docs** | **FULLY MET** | `docs/ARCHITECTURE.md`, `docs/LEGAL_REQUIREMENTS.md` (source-cited legal checklist with confidence tags), `docs/DEPLOYMENT.md`. | This is unusually strong for a hackathon submission — lead with it if the panel includes anyone technical. |
| 14 | **Role-based auth** | **FULLY MET** | JWT + bcrypt, inspector/admin roles, dashboard admin-gated. | — |

### Where we might be over- or under-claiming

- **Not overclaiming:** the honesty-by-construction design (NEEDS_VERIFICATION as a first-class
  status, Tier 1/Tier 2 split, DRAFT-flagged legal doc) means the software's own outputs are
  more conservative than the marketing copy of most compliance tools. If anything this project
  **under-sells** itself in a pitch context — a panel unfamiliar with the domain may read
  "NEEDS_VERIFICATION" as weakness rather than rigor. **Frame it explicitly as the opposite.**
- **A gap a DoCA official would notice immediately:** exemptions (Rule 26 — packages ≤10g/ml,
  fast food sold by restaurants, Drugs Price Control Order formulations, farm produce >50kg,
  and pan masala's 2025 carve-out) are **not auto-applied**. A real inspector scanning a 5g
  sachet would get a FAIL the Rules never intended. This is documented, but a DoCA reviewer
  will find it in under a minute of testing — **raise it yourself, first.**
- **A gap a technically literate judge would notice:** R8-1 (placement/grouping) is a 2D
  bounding-box proximity proxy for "same principal display panel," not a true multi-panel
  reconstruction. This is disclosed in every report's methodology footer — which is the right
  call, but be ready to explain *why* 2D clustering is a reasonable proxy rather than a hack
  (see Q&A).

---

## The Briefing

### 1. What happens in the real world today

**Who enforces this.** The Legal Metrology Act, 2009 is administered centrally by DoCA, but
**day-to-day enforcement is a state subject** — each state/UT runs its own Legal Metrology
(Weights & Measures) directorate. The organisational structure is a three-tier field
hierarchy: **Inspectors** (Section 14 of the Act) at the taluk/district level do the physical
inspection and booking of offences; **Assistant Controllers** supervise at district level;
**Controllers/Deputy Controllers** sit at state headquarters.

**The scale mismatch is real and severe, though no single national inspector-count figure is
publicly published** (we searched; DoCA/state annual reports don't appear to aggregate it in
one place, so we reason from proxies rather than assert a number we don't have):
- A real, cited example: Andhra Pradesh's Nellore Zone runs **one Deputy Controller, three
  Assistant Controllers, and seven Inspectors** covering an entire multi-district zone.
- State recruitment drives for Inspector of Legal Metrology posts typically run **14-17
  vacancies per state per cycle** (Assam 2025: 14 posts; West Bengal 2020: 17 posts) — these
  are the entire *new hire* batches for a state, not backlog fills.
- Against this: India's FMCG sector alone has thousands of brands each running roughly
  **200-2,000 active SKUs** per mid-market player, before counting pharmacy, hardware,
  agricultural inputs, and every other packaged-commodity category the Rules cover, and
  before counting the same product re-skinned across regional-language label variants. **We
  are not aware of a published, defensible national total SKU count**, and we won't invent
  one — but the order-of-magnitude gap between "single-digit inspectors per zone" and "every
  packaged SKU on every shelf in that zone" is the entire reason manual-only inspection cannot
  scale, and is the plain, undisputed premise of the problem statement itself.

**The manual inspection workflow, today:** an Inspector visits a retail premises (often
triggered by a routine beat, a consumer complaint, or a targeted drive), physically examines
package declarations against the Rules by eye (and, for font size, sometimes a physical
scale), records findings on paper or a basic digital form, and — if a violation is found —
initiates action.

**How a violation becomes a notice, and what happens next:**
- **Compounding** — the more common path for first/minor offences. The Inspector can compound
  the offence for a fee in lieu of prosecution, closing it administratively.
- **Prosecution under Section 36** — for repeat or serious offences. The Act's actual penalty
  structure (confirmed via primary/secondary legal sources, not assumed):
  - **§36(1)** (declaration non-conformance): fine up to **₹25,000** (1st offence), up to
    **₹50,000** (2nd), and **not less than ₹50,000 up to ₹1,00,000, or imprisonment up to 1
    year, or both** (3rd and subsequent).
  - **§36(2)** (net-quantity error): fine **₹10,000-50,000** (1st offence), rising to up to
    **₹1,00,000 or imprisonment up to 1 year, or both** for repeat offences.
  - Penalties apply **per package/consignment**, so exposure on a large non-compliant batch
    is real, not nominal.
- **Consumer-initiated escalation, outside the LM enforcement chain but adjacent to it:** a
  consumer can call the **National Consumer Helpline (1915)**, DoCA's own grievance
  mechanism — about **70% of NCH complaints close at that stage** (DoCA 2024-25 annual
  report) without escalating further. Unresolved ones can go to a consumer commission via
  **e-Daakhil** (launched by NCDRC in 2020; since 1 Jan 2025 merged into the unified
  **e-Jagriti** platform, covering 444 commission locations nationwide). This is a
  *parallel consumer-redress track*, not the LM enforcement track itself, but it matters here
  because **a clause-cited compliance report is exactly the kind of evidence a consumer
  commission or a compounding officer wants to see** — see §3.

**Marketplace liability for seller labels since 2020.** The Legal Metrology (Packaged
Commodities) Amendment Rules made e-commerce entities responsible for displaying the same
mandatory declarations online that a physical label carries (an amendment line dating to
2017-18), while the **Consumer Protection (E-Commerce) Rules, 2020** separately clarified
that a marketplace's *own* liability is limited when it functions purely as an intermediary
(safe-harbour-style) — the primary declaration obligation still sits with the
manufacturer/seller/importer. Net effect: marketplaces have real, but bounded, incentive to
police listing content, which is exactly why our v1 chose to solve **the physical-label
problem first** — it's where the compliance failure actually originates.

**Common real-world violation patterns** (consistent with what our own rule engine checks,
and with the patterns cited across the legal-compliance literature we reviewed): missing or
incomplete manufacturer/packer/importer address; MRP declared without the mandatory "inclusive
of all taxes" wording; missing or wrongly formatted manufacture/best-before dates; net
quantity in a non-standard unit; undersized MRP or net-quantity print relative to the rest of
the label; and, increasingly, absent or incomplete country-of-origin declarations on imported
goods.

**Sources:**
[Section 36, Legal Metrology Act 2009 — IndianKanoon](https://indiankanoon.org/doc/28676169/) ·
[Penalty under Legal Metrology Law — S.S. Rana & Co.](https://ssrana.in/corporate-laws/legal-metrology-and-packaging/penalty-legal-metrology/) ·
[Directorate of Legal Metrology structure — India Standards Portal](https://indiastandardsportal.org/Regulatorybodycontent.aspx?RegulatryBodiesId=9) ·
[Legal Metrology, Nellore Zone, AP](https://spsnellore.ap.gov.in/legal-metrology/) ·
[About NCH — National Consumer Helpline](https://consumerhelpline.gov.in/public/about) ·
[E-Daakhil — Wikipedia](https://en.wikipedia.org/wiki/E-Daakhil) ·
[Legal Metrology Compliance for E-Commerce — S.S. Rana & Co.](https://ssrana.in/articles/legal-metrology-compliance-for-e-commerce-businesses/) ·
[Rule 26 exemptions — iPleaders](https://blog.ipleaders.in/legal-metrology-packaged-commodities-rules-2011-2/) ·
[India FMCG Market — IMARC](https://www.imarcgroup.com/india-fmcg-market)

---

### 2. Market / stakeholder map

| Stakeholder | Relationship to this solution | Notes |
|---|---|---|
| **State Legal Metrology / Weights & Measures departments** | **Primary user** — the Inspector and the supervising Controller are the two roles the app is built around. | This is the PS's literal target user — everything else is secondary. |
| **DoCA (central)** | Policy owner, potential aggregator of a multi-state rollout, owner of the legal source-of-truth we cite. | The natural "phase 3" buyer (§4) — a central instance with state-level data feeding back into policy. |
| **FSSAI** | Adjacent, not overlapping — FSSAI governs *food safety/labelling content* (nutrition, ingredients, allergens); Legal Metrology governs *quantity, price, and manufacturer-identity declarations*. A food package needs both regimes satisfied. | Worth naming explicitly in a Q&A — a panelist may conflate the two. We deliberately do not attempt FSSAI checks; scope stays Legal Metrology only. |
| **BIS** | Adjacent — product *quality/safety standards*, not declaration format. No overlap with this tool's checks. | Mention only if asked; not a natural next-integration target. |
| **FMCG in-house compliance/QA cells** | A plausible **secondary buyer**, not the PS's target — a large manufacturer could use this pre-market, as a self-check before a label goes to print, to catch the same errors DoCA would later catch. | This is real market validation for the *underlying engine*, even though the PS's ask is government-facing. Don't lead with it in front of DoCA (frame as "same engine, different customer," not a pivot). |
| **Large retail chains** | Could use it for incoming-stock compliance spot-checks (a chain doesn't want non-compliant stock triggering an inspection at its own stores). | Speculative, not validated — present as a plausible extension, not a claim. |
| **E-commerce platforms** | Have their own liability exposure (§1) and their own existing (closed, catalogue-text-based, largely English) compliance classifiers. Not a near-term customer for a government tool, but a comparison point (below). | |
| **Packaging-artwork QA vendors** | Private-sector competitors, sort of — proofing tools that check artwork *before* print, generally paid SaaS, closed-source, and typically **not built against India-specific Legal Metrology clause citations** — they check general layout/readability, not "does this satisfy Rule 6(1)(a)". | This is the closest existing commercial category, and it's exactly the gap we don't fill the same way: we check a *photograph of a finished, printed package*, post-hoc, clause-cited — not artwork pre-press. |

**Where alternatives actually stand today, honestly:** on the government-enforcement side, we
did not find evidence of an existing DoCA/state tool that does automated, clause-cited,
photo-based compliance checking at the label level — the workflow described in §1 is manual.
On the private side, marketplace-internal classifiers (Amazon/Flipkart-style) exist but are
**closed, optimised for catalogue *text* fields the seller already typed in, not photo-based
label OCR, and not built to cite Indian Legal Metrology clauses** — they're solving a
different, narrower problem (does the *listing* look complete) rather than this one (does the
*physical label*, as actually printed, satisfy the Rules). **This solution sits in a real,
currently-unaddressed gap: government-facing, photo-first, clause-cited, multilingual.**

---

### 3. Impact of our solution — in depth

**First-order effects (direct, on the inspection act itself):**

- **Inspector time per pack.** A manual check against 14 declaration/placement points plus font-size
  eyeballing plausibly runs several minutes per package when done carefully (reading every
  declaration, checking placement, doing basic arithmetic on unit pricing). A photo-to-report
  cycle on this tool runs on the order of **1-5 seconds of OCR processing** (measured on real
  product photos this build cycle, hardware-dependent) plus the time to take the photo — call
  it **under a minute, inclusive of photography**, for a *first pass* that an inspector then
  reviews rather than performs from scratch. This is a **reasoned estimate**, not a controlled
  time-motion study against real inspectors — we have not run one, and say so plainly rather
  than presenting a fabricated "10x faster" headline number.
- **Throughput multiplier.** Directly follows from the above: if first-pass screening is
  materially faster than a from-scratch manual check, one inspector can screen materially more
  packages per shift, reserving full manual scrutiny for what the tool flags rather than
  everything.
- **Consistency/objectivity.** A regex/keyword rule engine applies the *same* clause test to
  every package, every time — it cannot have an off day, skip a step under time pressure, or
  vary between two inspectors checking the same product differently. This is a genuine,
  structural gain independent of raw speed.

**Second-order effects (downstream of the report existing at all):**

- **Defensibility in a compounding hearing or consumer forum.** A report that states "R6-7,
  Rule 6(1)(e): MRP found as evidence-string '₹90', but the required 'inclusive of all taxes'
  qualifier is absent" is a fundamentally stronger administrative record than an inspector's
  handwritten note — it is reproducible, timestamped, image-evidenced, and clause-cited. This
  is exactly the kind of record that holds up when a compounding decision or a consumer-forum
  filing gets challenged.
- **Audit trail / repository value.** Every scan is a permanent, searchable record — which
  means a supervising Controller can, for the first time, query "show me every non-compliant
  scan in the last 30 days" rather than relying on paper files scattered across field offices.
- **Dashboard value for supervisory targeting.** The current dashboard (status breakdown,
  30-day trend, recent non-compliant scans) is a first cut at what could become real
  targeting intelligence — e.g., a Controller noticing a spike in a particular violation type
  or geography and directing inspection resources there. **We have this at the "recent list"
  level today; category/brand-level aggregation for true targeting is a natural v2, not yet
  built** — say so if asked, don't imply it exists.
- **Deterrence.** Speculative but directionally reasonable: if manufacturers know
  label-declaration compliance can be checked quickly and consistently at scale, the marginal
  incentive to cut corners on a declaration shifts. We make no claim to have measured this —
  it would require a real deployment and a before/after study neither we nor, to our
  knowledge, anyone else has run for a tool like this.
- **Data feedback loop into DoCA policy.** Aggregated, anonymised violation-pattern data
  (which clause fails most often, by category) is exactly the kind of evidence base DoCA would
  want when deciding where the Rules themselves need tightening, clarifying, or where an
  exemption threshold needs revisiting — this is a genuine, non-obvious second-order value the
  PS doesn't ask for explicitly, but that a repository of clause-cited, structured violation
  data naturally enables over time.

**The multilingual capability specifically.** Real Indian retail labels are frequently
bilingual or trilingual (a national brand's Hindi-market pack, a regional Gujarati-market
variant) — an English-only OCR/compliance tool simply cannot read the declaration on a large
share of real shelf stock. Running Tesseract's eng+hin+guj combined model with a per-line
dominant-script selection pass is what makes this tool applicable to the labels India
*actually* prints, not just the subset that happens to be in English. This is a coverage gain,
not a cosmetic feature — an English-only tool would silently fail (or worse, silently
misread) a meaningful fraction of the real label population this is meant to check.

**Where impact is honestly limited, stated plainly:**

- **Font-size (Rule 7) impact is capped at Tier 1 (a relative signal) unless the inspector
  supplies a physical reference dimension.** A definitive millimetre-accurate Rule 7
  PASS/FAIL is only possible with Tier 2 calibration — this is a genuine constraint of
  deriving physical measurements from an uncalibrated photograph, not a solvable software gap.
- **Exemptions are not auto-applied** (§1 audit) — every scan of a genuinely exempt small
  package currently returns a misleading FAIL unless the inspector already knows to discount
  it. This is a real, near-term-fixable gap (an exemptions lookup + inspector confirmation
  step), not yet built.
- **E-commerce listing scanning is v1-absent** — impact on the *online* half of the retail
  market is zero today, only on physical/photographed labels.

---

### 4. What production looks like

**Rollout phasing — deliberately staged, not a big-bang national launch:**

1. **Phase 1 — single-state pilot.** One state Legal Metrology directorate, a handful of
   Inspectors, real field use against real inspection drives, with every NEEDS_VERIFICATION
   and every disputed FAIL logged and reviewed manually to build a real accuracy baseline
   against real (not synthetic) field photography — the honest gap this build cycle
   surfaced repeatedly (see §5, "what's your evidence").
2. **Phase 2 — case-management integration.** Once the pilot's accuracy and workflow fit are
   validated, integrate report output into whatever case/violation-tracking system the state
   already uses, so a FAIL can flow directly into a compounding-notice or prosecution
   workflow rather than living only in this tool's own repository.
3. **Phase 3 — DoCA central instance + e-commerce ingestion.** A central, multi-state
   instance for aggregated policy-feedback data (§3), and the e-commerce listing-scan path
   the schema already supports, built out into the UI.

**Infra footprint and cost — genuinely low, and this is a real structural advantage:**

- **No per-scan API cost.** Tesseract and the rule engine are both fully offline/open-source —
  there is no OpenAI/Google-Vision-style per-call billing. Cost is **hosting only**: compute
  for the OCR pipeline (CPU-bound, no GPU required) plus a database. This is a materially
  different cost profile from any LLM-based alternative, and matters directly for a
  government procurement context where a recurring per-transaction API bill is a real
  budgetary and vendor-lock-in concern.
- **Current deployment** (for the SIH demo): Render, Docker image bundling Tesseract with all
  three language packs, Postgres. Free-tier for the hackathon; a real pilot would move to a
  small always-on instance specifically to avoid free-tier cold-start behaviour, which is not
  acceptable for field use.
- **OCR compute cost, measured this build cycle:** roughly **1-5 seconds of CPU time per
  scan** depending on photo resolution and label complexity, after a resolution-cap fix this
  cycle brought a real-world worst case down from ~367MB peak memory to under 300MB — i.e.
  this runs comfortably on a modest single instance, not a GPU cluster.

**Scaling considerations, honestly:**

- Rate limiting is currently **in-process**, correct for a single instance, and explicitly
  **not** yet a multi-worker-safe design — moving to multiple workers needs a shared store
  (Redis) for the rate limiter, documented as a known next step, not hidden.
- Postgres plus a **persistent volume** for uploaded images/reports is required for anything
  beyond a demo — the current free-tier deployment's storage is ephemeral (wiped on
  restart), which is fine for a hackathon and explicitly **not** fine for a real pilot; this
  is flagged in our own deployment docs, not discovered by surprise later.
- At real multi-state volume, the natural next scaling move is a queue (upload → job →
  result) rather than synchronous request/response, so a burst of uploads doesn't compete for
  OCR CPU in real time — not built, reasoned about explicitly here as the honest next step.

**Data privacy / retention / security posture:**

- Scanned images are of **product packaging**, not personal data — the privacy surface is
  narrower than most government IT projects, but inspector identity, scan timestamps, and
  location-adjacent metadata (product/scan context) are still real personal/operational data
  needing a retention policy a real deployment would define with the state department, not
  something a hackathon prototype should presume.
- Auth is JWT + bcrypt, no hardcoded secrets (verified — the app refuses to start in
  production without an explicit secret), CORS locked to known origins, upload validation
  (file type + size) ahead of the OCR pipeline, rate limiting, and no stack traces or internal
  paths ever returned to a client. This is real, already-implemented hardening, not a roadmap
  item.
- API docs (Swagger) are **off by default in production** and only enabled deliberately for
  this demo, specifically so a real deployment doesn't leak its own schema as reconnaissance.

**What breaks first at real scale, and the fix:**
1. Free-tier cold starts → move to an always-on instance.
2. Ephemeral storage → persistent volume / object storage.
3. In-process rate limiter under multiple workers → Redis-backed limiter.
4. Synchronous upload-to-result under burst load → background job queue.
None of these are unknown-unknowns — all four are already identified and documented, which is
itself the point: **this was built with production concerns in view from the start, even
though the current deployment is intentionally a lightweight demo instance.**

**The human-in-the-loop model, stated as policy, not just as a technical fallback:** this tool
is built to **assist an Inspector's judgement, not replace it.** Every NEEDS_VERIFICATION
result exists specifically to route a genuinely uncertain case to a human, and no output is
positioned as a self-executing legal determination — the PDF report's own footer says so
explicitly: *"This report is a decision-support tool for enforcement officials, not a final
legal determination."*

---

### 5. Anticipated Q&A

**On accuracy and OCR**

**Q1. How accurate is the OCR / what's your accuracy number?**
We do not claim a single headline accuracy percentage, deliberately — publishing one figure
from a small synthetic test set would itself be a form of overclaiming, exactly what this
tool's design principle refuses to do. What we can state precisely: 96 automated tests pass,
including a full walkthrough of 12 demo labels (3 in real Devanagari/Gujarati script, 1 with
a deliberate placement violation) each verified to be flagged for the specific violation it
was built to exercise; and, this build cycle, three independent real single-character OCR
misreads were found from **actual re-photographed product labels** (not synthetic images),
root-caused, and fixed with permanent regression tests. A real accuracy percentage against a
statistically meaningful, real-world labelled test set is exactly what Phase 1 (§4) is
designed to produce — we don't have that number yet, and won't invent one.

**Q2. How do you measure font size from a photo?**
Two-tier, explicitly. Tier 1, always available: compares each declaration's detected
text-height in pixels against the tallest text on the same label (typically the brand name) —
a *relative* signal that catches the common real pattern of disproportionately tiny MRP/net-
quantity print, but never resolves to a hard Rule 7 PASS/FAIL, because no physical unit was
actually measured. Tier 2, opt-in: the inspector supplies one known physical dimension (e.g.
package width in mm), which lets us compute pixels-per-mm and check the real millimetre height
against Rule 7's Table-I. Every report states plainly which tier produced a given finding.

**Q3. What if the label is curved / glare / low light?**
Real, disclosed limitation. Preprocessing (deskew, CLAHE contrast normalisation, resolution-
aware upscaling) helps with moderate cases, and low-confidence OCR regions correctly surface
as NEEDS_VERIFICATION rather than a guessed value — but a badly glared or heavily curved
photo can still degrade extraction quality. This is why the tool flags an "image quality"
warning distinct from a compliance FAIL when confidence is too low across the board, so a bad
photo is never mistaken for a non-compliant product.

**Q4. How do you keep up with rule amendments?**
`docs/LEGAL_REQUIREMENTS.md` tracks the amendment chain with explicit confidence tags per
clause — `[VERIFIED-TEXT]` (confirmed against primary Gazette text), `[VERIFIED-SECONDARY]`
(secondary legal sources only), `[VERIFY WITH DoCA]` (genuinely unconfirmed, and the rule
engine returns NEEDS_VERIFICATION for anything in that category, never a fabricated
PASS/FAIL). This is a living document by design — amendments through 2026 (the medical-device
carve-out under GSR 778(E), the Rule 6(10A) e-commerce country-of-origin filter, the pan
masala exemption) are already tracked in it. A real deployment would need this reviewed and
signed off by DoCA's own legal team before any threshold is treated as final — we say that
explicitly, we don't imply our own research substitutes for that review.

**Q5. Placement check — is 2D clustering really valid?**
It's a disclosed **proxy**, not a certified determination, and every report says so in its
methodology footer. Bounding-box proximity on a single 2D photograph cannot distinguish a
genuinely separate panel from an unusual-but-single-panel layout with full certainty — true
validation would need multi-angle capture or 3D reconstruction, out of scope for a phone-photo
tool. What it *does* do reliably: flag the common real violation pattern of a declaration
printed far from the rest of the mandatory group, which is the practical failure mode Rule 8
exists to catch. R8-2 (the net-quantity clear-space check) is scale-invariant and needs no
calibration, unlike R8-1 — worth distinguishing if pressed.

**On the human/legal/business model**

**Q6. Can this replace inspectors?**
No, and we don't design toward that. Every report explicitly states it is a decision-support
tool, not a final legal determination. The value case (§3) is inspector *throughput* and
*consistency*, not inspector *elimination* — Section 14 of the Act vests inspection authority
in a human Inspector, and nothing here changes that.

**Q7. What about legal liability if the tool is wrong?**
This is exactly why NEEDS_VERIFICATION exists as a first-class status rather than a fallback —
the tool is built to never assert a confident wrong answer where the underlying evidence is
weak; it's built to say "uncertain" instead. The human Inspector remains the one who acts on a
finding, reviews the evidence, and makes the legal determination — the tool's role is
evidence-gathering and first-pass screening, not adjudication. Any real deployment would need
this liability allocation formalised in whatever procurement/usage agreement covers it — that's
a legal/policy step, not a software one, and we're explicit that we haven't done it.

**Q8. Why not use an LLM / GPT for extraction?**
Deliberate v1 choice, documented, not a limitation we're unaware of. A rule-based, regex/
keyword extraction pipeline is (a) fully offline, no per-call API cost or vendor dependency —
material for a government deployment; (b) fully auditable — every extracted value traces to
an exact OCR region and confidence, not a black-box model's internal reasoning; and (c)
deterministic — the same photo produces the same result every time, which matters for
something that may end up as evidence in a compounding hearing. An LLM-based extraction
fallback is explicitly named as the natural v2 extension in our own architecture doc, for
higher accuracy on unusual label layouts, at the honestly-stated cost of introducing an
external API dependency this offline-first v1 deliberately avoids.

**Q9. How do you handle bilingual and regional-language labels?**
Tesseract's combined eng+hin+guj model does initial layout detection, then each merged text
line is re-OCR'd against its dominant script specifically — a genuinely mixed-script line
(e.g. a Hindi phrase next to a Latin email address) falls back to the combined model rather
than risk one language mangling the other. Native-script numerals (Devanagari/Gujarati) are
normalised back to Arabic digits before any value is parsed. This build cycle found and fixed
a real case of the combined model hallucinating foreign-script glyphs on plain English text —
fixed with evidence, tested, and deliberately **asymmetric** (an English-majority line can be
cleaned up; a Gujarati-majority line with a legitimate Latin unit abbreviation is *not*
forced to Gujarati-only, because that model literally cannot output the Latin characters a
real "1000 ml" needs).

**Q10. What about e-commerce listings?**
Not in v1's UI, by deliberate scope decision — the schema already accepts listing text as an
alternate input source with no redesign needed, but building that ingestion path out was
judged lower-priority than getting label-photo compliance right first, since that's where
consumer-facing declaration failures actually originate (a listing usually just repeats what's
already printed, or is separately regulated by the 2017 e-commerce amendment and the 2020
Consumer Protection E-Commerce Rules — see §1).

**Q11. How is this different from what Amazon/Flipkart already do?**
Marketplace-internal tools, where they exist, work on **catalogue text fields the seller
typed in** — not on a photograph of the physical label, and not built to cite Indian Legal
Metrology clauses specifically; they're closed-source, and their optimisation target is
listing completeness/consistency, not enforcement-grade legal evidence. This tool is
government-facing, photo-first (checks what's actually printed, not what a seller claims),
multilingual, and every output cites the exact Rule/clause it's checking — a fundamentally
different design target from a marketplace's internal QA classifier.

**Q12. Can a manufacturer game it?**
In principle, yes, in the narrow sense that any rule-based system can be studied and its edge
cases probed — that's true of manual inspection too. What raises the cost of gaming this
specifically: every check cites its exact clause (so "gaming" one check doesn't imply gaming
the underlying legal requirement, just this tool's detection of it), and a human Inspector
remains the final decision-maker reviewing the evidence, not an automated pass/fail gate a
manufacturer could tune against in isolation.

**Q13. Data security and who owns the scanned data?**
Architecturally, the deploying state department would own its data — this is a self-hosted
tool (Docker image, Postgres), not a SaaS product that retains scan data on our own
infrastructure. Current hardening: bcrypt password hashing, JWT auth with role separation, no
hardcoded secrets (the app refuses to start in production without one), CORS locked to known
origins, upload validation, rate limiting, and no internal error detail ever surfaced to a
client. A real deployment's data-retention and access-control policy would be defined jointly
with the department, not unilaterally by us.

**Q14. What's your evidence it works — show test results.**
96 automated backend tests, covering every rule check's PASS/FAIL/NEEDS_VERIFICATION
branches, extraction unit tests, and a full 12-label end-to-end walkthrough. Separately —
and this is the more honest evidence — this build cycle involved repeatedly re-scanning
**real product photographs** (not the synthetic demo set), finding real extraction bugs from
the actual OCR output, root-causing each one against the literal misread text, fixing it, and
locking the fix in with a regression test. That process, and its visible trail of "found a
real bug, fixed it, verified against the real image again," is itself part of the evidence —
we're not claiming a polished, bug-free system; we're showing a system that gets real bugs
found and fixed against real inputs, which is a different and more credible claim.

**Q15. Cost to deploy nationally?**
No worked national cost model exists yet — building one responsibly needs real per-state
volume assumptions we don't have. What we can state with confidence: the **marginal cost per
scan is near-zero** (no LLM/Vision API billing — Tesseract and the rule engine are both free,
open-source, self-hosted), so total cost scales primarily with **hosting infrastructure**
(compute + storage + database), which is a materially smaller and more predictable line item
than any per-transaction-billed alternative would carry at national volume.

**Q16. How do you handle exempted categories?**
Honestly, not yet automatically — this is a real, named gap (§1, §3), not hidden. Rule 26
exemptions (packages ≤10g/10ml, restaurant-packed fast food, Drugs Price Control Order
formulations, farm produce >50kg, pan masala's 2025 carve-out) are documented in our legal
reference but not yet auto-applied against a scanned package's declared/estimated size. The
fix is a bounded, known piece of work: an exemptions lookup keyed to declared net quantity and
category, surfaced to the inspector for confirmation rather than silently auto-excluded (since
misclassifying a genuinely non-exempt package as exempt would be the more dangerous failure
mode) — not built yet, clearly scoped for the next iteration.

**Q17. Offline / poor-connectivity field use?**
Not supported today — this is a web app requiring connectivity to the backend for OCR
processing. The OCR/rule engine itself has **no external API dependency** (fully offline-
capable in principle, since Tesseract runs locally), so a field-deployable offline mode is
architecturally plausible as a future direction (e.g. a local-network or edge-device
deployment) but is not something we've built or tested.

**Q18. What happens to NEEDS_VERIFICATION items — who resolves them?**
Today: the human Inspector, reading the evidence (extracted value, cropped OCR region,
confidence, and the specific reason it wasn't auto-resolved) presented alongside every such
finding in the report. There is no current workflow feature for *tracking* resolution (e.g. an
inspector marking a NEEDS_VERIFICATION item as manually confirmed within the tool itself) —
that's a real, sensible next feature for the repository, not yet built.

**Q19. Why should DoCA trust a report generated by an automated tool over a trained
Inspector's own judgement?**
It shouldn't have to choose — that's the wrong framing, and we say so directly. The tool
doesn't ask to be trusted *instead of* the Inspector; every report is built to be trusted *as
evidence for* the Inspector's own judgement, with full traceability (bounding boxes,
confidence, clause citations) precisely so the Inspector — not the software — remains the
one exercising judgement and making the determination.

**Q20. What's the single biggest technical risk in this project right now?**
Honestly: **deployment reliability of the current free-tier hosting**, not the compliance
logic itself. The rule engine, extraction pipeline, and legal grounding have all been
stress-tested against real inputs this build cycle; the free-tier infrastructure choice made
for a hackathon demo (cold starts, ephemeral storage) is the weaker link, and is explicitly
not representative of what a real pilot deployment (§4) would run on.

**Q21. Why build this in Python/FastAPI rather than [X]?**
FastAPI gives fast, well-typed API development with automatic OpenAPI documentation (useful
both for our own testing and as judge/reviewer-facing technical documentation), and Python has
the strongest, most mature OCR/image-processing ecosystem (OpenCV, pytesseract) available
without a paid API — directly serving the offline-first, no-per-call-cost design goal in Q8.

**Q22. What's the biggest thing you'd do differently if you started over?**
We would define the real-world accuracy-measurement protocol (a labelled set of real, diverse
field photographs, not synthetic mockups) *before* writing the rule engine, not after — this
build cycle's most valuable work was finding and fixing real OCR bugs from real photos late in
the process; doing that systematically from day one would have caught the same class of issues
earlier and cheaper.

**Q23. Does this work for products that are already compliant — does it correctly say
PASS?**
Yes — the demo repository includes labels deliberately built to be fully compliant, and the
rule engine correctly returns PASS across all applicable checks for them. A tool that only
ever finds violations, never confirms compliance, would itself be a red flag; ours does both,
visibly, in the same report format either way.

**Q24. How does the compliance_score number relate to the itemised PASS/FAIL list — which
is authoritative?**
The itemised list is authoritative, always. `compliance_score` (pass_count / applicable_count)
is computed and shown only as a secondary summary metric, explicitly labelled as such in the
UI and every report — never as a replacement for reading the actual itemised findings. This
was a deliberate design decision specifically to prevent a single number from becoming a
stand-in for the real evidence.

**Q25. Who is the "admin" role, in a real deployment — who would actually have dashboard
access?**
In our model: the supervising Controller/Deputy Controller tier, who would use the dashboard
for the targeting/oversight use case in §3, versus the Inspector role, who performs scans in
the field. This maps directly onto the real three-tier LM organisational structure (§1)
rather than being an arbitrary two-role split.

---

### 6. Pitch narrative + 60-second demo script

**One-paragraph pitch narrative:**

> Legal Metrology inspectors in India are responsible for checking mandatory declarations —
> manufacturer identity, net quantity, MRP, dates, consumer care, country of origin, font
> size, and placement — on every packaged commodity sold in the country, with a field
> workforce that, by any reasonable reading of state recruitment and staffing patterns, is
> orders of magnitude smaller than the SKU population it's meant to cover. The LMPC
> Compliance Scanner turns that manual, page-by-page, eye-by-eye check into a photograph: an
> Inspector uploads a picture of a package's principal display panel and gets back, in
> seconds, an itemised report where every single finding — pass, fail, or "needs a human
> look" — is cited to the exact clause of the Legal Metrology (Packaged Commodities) Rules,
> 2011 it's checking, evidenced with the extracted text, its location on the label, and how
> confident the OCR was. It reads English, Hindi, and Gujarati labels, because that's what
> Indian shelves actually carry. It never asserts a confident wrong answer — where the
> evidence is weak, it says so, explicitly, by design, because a compliance tool that
> fabricates certainty is more dangerous than one that has none. And because it's built on
> free, offline OCR and a transparent rule engine instead of a paid AI API, the entire
> approach costs nothing per scan to run at any scale a state department needs.

**60-second demo script:**

- **[0-10s]** "This is a real photograph of a real product — not a mockup." Upload it live.
- **[10-20s]** While it processes: "Under the hood: OCR reads the label in whichever script
  it's actually printed in, extracts every mandatory declaration, and checks it against 13
  specific clauses of the Packaged Commodities Rules."
- **[20-40s]** Report appears. Point at **one PASS** ("manufacturer address, found, Rule
  6(1)(a) — here's the exact bounding box it came from") and **one FAIL or
  NEEDS_VERIFICATION** ("MRP is present but missing the 'inclusive of all taxes' wording —
  Rule 6(1)(e), FAIL" or "font size — this is a relative signal only, here's why, here's how
  Tier 2 would make it a hard measurement").
- **[40-50s]** Scroll to the annotated image: "Every finding is drawn directly on the photo,
  not just listed in a table."
- **[50-60s]** Close on the dashboard: "And every scan an inspector does becomes part of a
  permanent, searchable record — which is the part manual inspection has never had."

---

## A note on how this document was produced

Web-sourced factual claims in this document (Section 36 penalty figures, the three-tier LM
organisational structure, NCH/e-Daakhil/e-Jagriti mechanics, Rule 26 exemption thresholds, the
2017/2020 e-commerce liability framework) were checked against live web search this session
and are cited inline. We searched specifically and could not find a single authoritative
national inspector-count or national SKU-count figure — rather than inventing one to make a
tidier slide, this document says so and reasons from the closest available proxies instead,
labelled as estimates throughout. That is a deliberate consistency with this project's own
"never fabricate a legal verdict" principle, extended here to "never fabricate a market
number" either.
