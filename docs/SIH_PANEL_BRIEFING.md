# SIH26034 — Panel & DoCA Briefing Document

**Who this is for:** the SIH 2026 final panel, and possibly officials from the Department of
Consumer Affairs (DoCA), Ministry of Consumer Affairs, Food & Public Distribution.

**What we built:** LMPC Compliance Scanner — a web app that scans a photo of a packaged
product's label and checks it against the Legal Metrology (Packaged Commodities) Rules, 2011,
producing a report where every finding is tied to the exact rule it's checking.

**The one rule this whole project follows:** never fabricate a legal verdict. If something is
an estimate, we say so. If the software can't verify something, it says "needs verification"
instead of guessing. This document holds itself to the same standard.

---

## TASK 1 — How well do we cover the problem statement?

Checked item by item against what SIH26034 asked for.

| # | What was asked | Status | Why | What a panel might push on |
|---|---|---|---|---|
| 1 | Scan **labels/images** | **Done** | Real OCR (Tesseract, English+Hindi+Gujarati), not a mockup — upload → clean up image → OCR → extract fields → check rules, tested on real product photos. | Ask them to hand you a product to scan live. This is your strongest moment if it works. |
| 2 | Scan **e-commerce listings** | **Partly done** | The data model already supports listing text as an input with no redesign — but the UI doesn't accept one yet. This was a deliberate v1 choice. | If asked "does it do e-commerce": say yes, honestly not yet, and explain why (§3 — the physical label is the harder, more valuable problem, so we solved that first). |
| 3 | **Check declarations** against the Rules | **Done** | 14 checks covering Rule 6 (mandatory declarations), Rule 7 (font size), Rule 8 (placement) — each one returns PASS/FAIL/NEEDS VERIFICATION with the exact clause it's checking. | Show the rule engine citing its clause live, not on a slide. |
| 4 | **Flag violations** | **Done** | Every FAIL comes with the extracted text, where it was found on the image, and how confident the OCR was. | — |
| 5 | Check **font size / readability** | **Partly done, and we say so** | Two tiers: Tier 1 (no setup needed) gives a relative comparison only, never a hard PASS/FAIL. Tier 2 (inspector enters one real measurement) gives an actual millimetre check. | **Most likely tough question you'll get** — bring it up yourself before they ask (see Q2). |
| 6 | Generate **reports** | **Done** | A PDF (with the annotated photo) and an editable Word doc. | — |
| 7 | **Repository + history** | **Done** | Every scan is saved — raw OCR text, extracted fields, results, all images, both report files. Searchable by text, status, date. | — |
| 8 | **Dashboard** for officials | **Done** (admin only) | Total scans, pass/fail breakdown, 30-day trend, 10 most recent non-compliant scans. | They may ask for smarter targeting (e.g. worst offenders by brand) — we have recency, not that yet. Say so. |
| 9 | **Web/mobile app** | **Partly done** | Works fine on a mobile browser. Not a native app — no offline mode, uses the browser's normal file picker for the camera. | If asked "is there an app": no, and that's a reasonable choice — wrapping a working web backend into a native app is packaging, not a rebuild. |
| 10 | **Automatic extraction** | **Done** | Every field is pulled out automatically with its own location and confidence — no manual typing. | — |
| 11 | **Rule-based checking** | **Done** | Every verdict traces back to one exact clause — a strength, not a weakness (see Q8, why not an LLM). | — |
| 12 | **Search** | **Done** | Full search on the repository. | — |
| 13 | **Documentation** | **Done** | Architecture doc, a source-cited legal reference doc, a deployment guide. | Unusually thorough for a hackathon — lead with it for a technical judge. |
| 14 | **Role-based login** | **Done** | Password login with inspector/admin roles; dashboard is admin-only. | — |

### Where we might be over- or under-selling ourselves

- **We're probably under-selling it.** Being honest about uncertainty (NEEDS VERIFICATION,
  the Tier 1/2 split) can look like weakness to someone unfamiliar with the space, when it's
  actually the opposite — most compliance tools would just guess. Frame it that way out loud.
- **A DoCA official will spot this in a minute:** small-package exemptions (Rule 26 — packs
  under 10g/10ml, restaurant food, certain drug formulations, farm produce over 50kg, pan
  masala's 2025 exemption) aren't applied automatically yet. A tiny sachet would wrongly get a
  FAIL. It's documented — raise it yourself first.
- **A technical judge will spot this:** the placement check (are all declarations grouped
  together) works by measuring distance on the 2D photo, not by truly understanding panel
  layout. We say so in every report. Be ready to explain why that's still a reasonable
  approach, not a shortcut.

---

## The Briefing

### 1. How this actually works in the real world today

**Who enforces this.** The Legal Metrology Act, 2009 is a central law, but day-to-day
enforcement is done by each state's own Legal Metrology department. Inspectors do the physical
checking, Assistant Controllers supervise them, and Controllers sit at the state level.

**The staffing gap is real, even without one clean national number** (we looked — no single
published figure exists, so here's what we found instead):
- Andhra Pradesh's Nellore Zone runs on **one Deputy Controller, three Assistant Controllers,
  and seven Inspectors** for an entire multi-district zone.
- States typically hire only **14-17 new Inspectors per recruitment cycle** (Assam 2025: 14;
  West Bengal 2020: 17) — and that's the whole new-hire batch, not filling a backlog.
- Meanwhile a single mid-size FMCG brand can carry **200-2,000 active products**, before
  counting every other packaged-goods category and every regional label variant. We don't
  have (and won't invent) a national product-count figure, but the gap between "a handful of
  inspectors per zone" and "every product on every shelf" is exactly why manual-only
  inspection can't keep up — that's the premise the problem statement itself is built on.

**How a manual check works today:** an Inspector visits a shop, checks the label by eye
(sometimes with a physical ruler for font size), writes it down on paper or a basic form, and
acts if something's wrong.

**What happens after a violation is found:**
- **Compounding** — the common path for small/first offences: pay a fee, case closed
  administratively.
- **Prosecution** — for repeat or serious cases, under Section 36 of the Act:
  - Wrong/missing declarations: fine up to ₹25,000 (1st offence), up to ₹50,000 (2nd), and
    ₹50,000-1,00,000 or up to 1 year in jail (3rd+).
  - Wrong net quantity: ₹10,000-50,000 (1st offence), rising to ₹1,00,000 or up to 1 year in
    jail for repeats.
  - These fines apply per package/batch, so a large non-compliant shipment adds up fast.
- **Separately, consumers can complain too** — via the National Consumer Helpline (1915).
  About 70% of those complaints get resolved at that stage without going further. The rest can
  go to a consumer commission through the e-Jagriti platform (merged from e-Daakhil in 2025).
  This is a different track from formal enforcement, but a clause-cited report from this tool
  is exactly the kind of evidence that helps here too.

**E-commerce sellers have their own rules since 2020** — marketplaces must show the same
mandatory declarations online that the physical label carries, but a marketplace's own
liability is limited when it's just hosting a listing; the seller/manufacturer stays
responsible. That's part of why we chose to solve the physical-label problem first — that's
where the compliance failure actually starts.

**Common real violations** (consistent with what our rule engine checks): missing or
incomplete manufacturer address; MRP shown without "inclusive of all taxes"; missing or badly
formatted dates; net quantity in the wrong unit; MRP or net quantity printed too small; and,
increasingly, missing country-of-origin on imported goods.

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

### 2. Who this is for

| Who | How they relate to this | Notes |
|---|---|---|
| **State Legal Metrology departments** | **The main user** — Inspectors and Controllers are who the app is built around. | This is literally who the problem statement asks us to serve. |
| **DoCA (central)** | Sets the policy this is built on; a natural buyer for a multi-state version down the line. | Natural "phase 3" (see §4). |
| **FSSAI** | Related but different — FSSAI checks food safety/nutrition labelling, we check quantity/price/manufacturer info. A food package needs both. | Worth clarifying if a panelist mixes the two up. We deliberately don't check FSSAI rules. |
| **BIS** | Different again — product quality/safety standards, not label declarations. No overlap here. | Only mention if asked. |
| **Brand compliance/QA teams** | A possible second customer, not who the problem statement targets — a manufacturer could use this to self-check labels before printing. | Real extra value, but don't lead with it in front of DoCA — same engine, different customer, not a pivot. |
| **Large retail chains** | Could use it to spot-check incoming stock before it causes trouble in-store. | Just a plausible idea, not something we've validated. |
| **E-commerce platforms** | Have their own liability and their own closed-source, text-based compliance checks already. Not a near-term customer, just a useful comparison. | |
| **Packaging/artwork QA vendors** | The closest thing to a competitor — but they check artwork *before* printing, generally not tied to specific Indian Legal Metrology clauses. | We check a *photo of the finished, printed package*, after the fact, clause by clause — a different job. |

**Is anyone already doing this?** On the government side, we didn't find an existing DoCA or
state tool that does automatic, clause-cited, photo-based label checking — today it's manual.
On the private side, marketplace tools (Amazon/Flipkart-style) exist, but they check the
**text a seller typed into a listing**, not a photo of the actual label, and they're not tied
to Indian Legal Metrology clauses. **This is a real, currently-unfilled gap: government-facing,
works from a photo, cites the exact law, and reads multiple languages.**

---

### 3. What difference this actually makes

**Direct effects, on the inspection itself:**

- **Time per package.** A careful manual check — 14 declaration/placement points plus
  eyeballing font size — plausibly takes several minutes. This tool processes a photo in
  **1-5 seconds** (measured on real product photos), so the whole thing, photo included, is
  **under a minute** for a first pass an inspector then reviews. This is a reasonable estimate,
  not a formal study against real inspectors — we haven't run one, and we're not claiming a
  made-up "10x faster" number.
- **More packages checked per shift.** Follows directly: if the first pass is faster, one
  inspector can screen more products, saving deep manual review for what the tool actually
  flags.
- **Consistency.** A rule engine checks every package the same way, every time. It doesn't get
  tired, skip a step, or judge two identical products differently. That's a real gain on its
  own, separate from speed.

**Knock-on effects, once the report exists:**

- **Stronger evidence.** A report that says "MRP found as '₹90', but missing the required
  'inclusive of all taxes' wording, Rule 6(1)(e)" holds up much better in a compounding hearing
  or consumer case than a handwritten note — it's reproducible, timestamped, and cites the law.
- **A real audit trail.** Every scan is saved and searchable, so a Controller can finally ask
  "show me every non-compliant scan from the last 30 days" instead of digging through paper.
- **Early-stage targeting for supervisors.** The dashboard already shows status and trends; a
  Controller noticing a spike in one type of violation could send inspectors there. Aggregating
  by brand or category is a natural next step, not built yet — say so if asked.
- **Deterrence, probably, but unmeasured.** If brands know labels can be checked quickly and
  consistently, that's some incentive to get it right the first time. We haven't measured this,
  and doing so would need a real deployment and a before/after study nobody has run yet.
- **Feeds back into policy.** Aggregated, anonymised data on which clause fails most often, and
  where, is exactly the kind of evidence DoCA would want when deciding whether a rule needs
  tightening or an exemption threshold needs revisiting.

**Why multiple languages matters.** Real Indian labels are often bilingual or trilingual — a
Hindi-market pack, a Gujarati-market variant of the same product. An English-only tool would
simply fail to read a large chunk of real shelf stock. Running Tesseract across
English+Hindi+Gujarati, picking the right script line by line, is what makes this usable on
labels India actually prints — not a nice-to-have.

**Where the impact is honestly limited:**

- **Font-size checking stays a relative signal (Tier 1)** unless the inspector provides one
  real measurement (Tier 2). A confident, millimetre-accurate verdict needs that input — this
  is a real limit of measuring physical size from an uncalibrated photo, not something more
  code can fix.
- **Exemptions aren't applied automatically yet** (§1) — a genuinely exempt small package can
  still come back as a misleading FAIL today unless the inspector already knows to ignore it.
  Fixable, just not built yet.
- **E-commerce listings aren't scanned yet** — zero impact on the online half of retail today,
  only on photographed physical labels.

---

### 4. What running this for real would look like

**Rollout — staged, not a big national launch on day one:**

1. **Phase 1 — one state, pilot.** A single state's Legal Metrology department, a few
   Inspectors, real field use, every uncertain or disputed result logged and manually reviewed
   to build a real accuracy baseline from real field photos — the honest gap we kept running
   into this build cycle (see Q1).
2. **Phase 2 — plug into case management.** Once the pilot proves accurate and usable, feed
   report output into whatever system the state already uses to track violations, so a FAIL
   can flow straight into a compounding notice instead of just sitting in our own repository.
3. **Phase 3 — a central DoCA instance, plus e-commerce.** One instance aggregating data across
   states for policy feedback, and building out the e-commerce listing-check path the data
   model already supports.

**Running cost — genuinely low, and that matters:**

- **No per-scan API bill.** Tesseract and the rule engine are both free and run entirely
  offline — no OpenAI/Google-Vision-style charge per call. The only real cost is hosting:
  compute (no GPU needed) plus a database. That's a very different, much more predictable cost
  profile than any AI-API-based alternative, which matters a lot for government procurement.
- **Current setup (for this demo):** Render, a Docker image with all three language packs
  bundled, Postgres. Free tier for the hackathon; a real pilot would move to an always-on
  instance to avoid free-tier cold starts, which wouldn't be acceptable in the field.
- **Measured cost:** roughly 1-5 seconds of CPU time per scan, and a memory fix this cycle
  brought the real-world worst case down from ~367MB to under 300MB — this runs comfortably on
  one modest server, not a GPU cluster.

**Scaling — the honest version:**

- Rate limiting currently lives in a single process — fine for one instance, not yet safe
  across multiple workers, which would need a shared store like Redis. Known, documented, not
  hidden.
- A real pilot needs Postgres plus persistent storage for images/reports — the current
  free-tier demo's storage gets wiped on restart, which is fine for a hackathon and clearly not
  fine for real use. Already flagged in our own deployment notes.
- At real multi-state volume, the natural next step is a job queue (upload → process later →
  result) instead of making someone wait on the request — not built, but the obvious next move.

**Data privacy and security:**

- Scanned images are of packaging, not people — a narrower privacy surface than most
  government IT projects. Inspector identity, timestamps, and scan context are still real data
  that would need a retention policy agreed with the department, not something we'd assume.
- Already built: bcrypt password hashing, JWT login with role separation, no hardcoded secrets
  (the app refuses to start in production without one set), CORS locked to known origins,
  upload validation, rate limiting, and no internal errors ever shown to the user. This is
  already done, not a future promise.
- API docs are off by default in production, only turned on deliberately for this demo, so a
  real deployment doesn't expose its own API structure for free.

**What would break first at real scale, and the fix:**
1. Free-tier cold starts → move to an always-on server.
2. Storage wiped on restart → persistent storage.
3. Single-process rate limiter → Redis-backed one, for multiple workers.
4. Uploads processed synchronously → a background job queue under heavy load.
None of this is a surprise — all four are already known and written down. That's the point:
this was built with production in mind from the start, even though today's deployment is
intentionally a lightweight demo.

**This tool assists an Inspector — it doesn't replace one.** Every NEEDS VERIFICATION result
exists to send a genuinely uncertain case to a human. Nothing here claims to be a final legal
decision — the PDF report itself says so: *"This report is a decision-support tool for
enforcement officials, not a final legal determination."*

---

### 5. Questions we expect, and honest answers

**On accuracy and OCR**

**Q1. What's your accuracy number?**
We're not giving one headline percentage — publishing a number from a small test set would
itself be a kind of overclaiming, which is exactly what this tool is built to avoid. What we
can say precisely: 119 automated tests pass, including a full run through 12 demo labels (3 in
real Devanagari/Gujarati script, one with a deliberate placement violation), each correctly
flagged for the exact violation it was built to test. This build cycle we also found and fixed
several real bugs from **actual re-photographed products** (not synthetic images) — root-caused
and locked in with permanent tests. A real accuracy number, from a real labelled test set, is
exactly what Phase 1 (§4) is meant to produce — we don't have it yet and won't make one up.

**Q2. How do you measure font size from a photo?**
Two tiers. Tier 1 (always on): compares each declaration's text height in pixels to the tallest
text on the label — catches the common case of tiny MRP/net-quantity print, but never becomes
a hard PASS/FAIL, since no real-world unit was measured. Tier 2 (opt-in): the inspector enters
one known physical measurement (like the package width in mm), which lets us convert pixels to
millimetres and check against the Rules' actual size table. Every report states plainly which
tier produced a given result.

**Q3. What about a curved label, glare, or bad lighting?**
A real, disclosed limitation. Image cleanup (straightening, contrast fixing, zooming in on
small text) helps with moderate cases, and low-confidence readings correctly come back as
NEEDS VERIFICATION instead of a guess — but a badly glared or heavily curved photo can still
hurt accuracy. That's why we added a separate "image quality too low" result, so a bad photo
is never mistaken for a non-compliant product.

**Q4. How do you keep up when the Rules change?**
Our legal reference doc tracks every amendment with a confidence label per clause — confirmed
against the primary legal text, confirmed only via secondary sources, or genuinely unconfirmed
(in which case the rule engine always returns NEEDS VERIFICATION, never a guess). It's a living
document — recent changes like the medical-device carve-out and the pan masala exemption are
already tracked. A real deployment would need DoCA's own legal team to review and sign off
before treating any of it as final — we say that outright, we don't treat our own research as
a substitute for that.

**Q5. Is checking "are all the declarations grouped together" with 2D distance actually valid?**
It's a disclosed stand-in, not a certified check, and every report says so. Measuring distance
on a single 2D photo can't perfectly tell a genuinely separate panel from an unusual single-panel
layout — real certainty would need multiple angles or 3D reconstruction, out of scope for a
phone photo. What it does reliably do: catch the common real problem of a declaration printed
far away from the rest of the group. The separate net-quantity clear-space check doesn't need
any of this and works at any scale — worth mentioning if pushed on this.

**On the human, legal, and business side**

**Q6. Can this replace inspectors?**
No, and it's not built to. Every report says clearly it's a decision-support tool, not a legal
determination. The value (§3) is speed and consistency, not replacing the person — the law
itself gives inspection authority to a human Inspector, and nothing here changes that.

**Q7. Who's liable if the tool gets it wrong?**
This is exactly why NEEDS VERIFICATION exists — the tool is built to say "uncertain" rather
than confidently assert a wrong answer. The human Inspector still reviews the evidence and
makes the actual legal call — the tool gathers evidence and does a first pass, it doesn't
decide. A real deployment would need this liability question settled formally in a procurement
agreement — that's a legal/policy step we haven't done, and we say so.

**Q8. Why rules and regex instead of an LLM?**
A deliberate choice, not something we overlooked. Rule-based extraction is: (a) fully offline,
no per-call API cost or vendor lock-in — important for government use; (b) fully explainable —
every value traces back to an exact spot on the image and a confidence score, not a black box's
internal reasoning; (c) deterministic — the same photo gives the same result every time, which
matters if this ever becomes evidence in a hearing. An LLM-based fallback for tricky layouts is
a reasonable v2 idea, at the honest cost of adding an external API dependency this offline-first
version deliberately avoids.

**Q9. How do you handle Hindi and Gujarati labels?**
Tesseract's combined model does the first pass, then each detected line is re-checked against
its actual language specifically — a genuinely mixed-language line (say, Hindi text next to an
English email address) falls back to the combined model rather than risk one language mangling
the other. Native-script numerals get converted to normal digits before anything is parsed.
This build cycle we also found and fixed a real case of the model hallucinating foreign
characters into plain English text — fixed carefully so it only cleans up English-majority
lines, never forces a Gujarati line with a real "1000 ml" into losing its Latin letters.

**Q10. What about e-commerce listings?**
Not in the UI yet — a deliberate scope call. The data model already accepts listing text as an
alternate input with no redesign needed, but we prioritised getting label-photo checking right
first, since that's where declaration failures actually start (a listing usually just repeats
what's printed, and is separately covered by 2017/2020 e-commerce rules — see §1).

**Q11. How is this different from what Amazon/Flipkart already do?**
Their tools, where they exist, check the **text a seller typed into a listing** — not a photo
of the actual label — and aren't built to cite Indian Legal Metrology clauses; they're closed
source, and their goal is listing completeness, not enforcement-grade evidence. This tool is
government-facing, works from a photo of what's actually printed, reads multiple languages, and
every result cites the exact rule — a genuinely different job.

**Q12. Could a manufacturer game the system?**
In principle, any rule-based system's edge cases can be studied and probed — true of manual
inspection too. What raises the cost of trying: every check cites its exact legal clause, so
gaming one check doesn't mean gaming the actual law behind it, and a human Inspector still
reviews the evidence and makes the final call, not an automated gate a manufacturer could tune
against alone.

**Q13. Who owns the scanned data, and how secure is it?**
Whichever state department deploys it owns the data — this is a self-hosted tool (Docker +
Postgres), not a SaaS product that keeps data on our servers. Already built: password hashing,
JWT login with role separation, no hardcoded secrets, CORS locked down, upload validation, rate
limiting, and no internal errors ever shown to a user. Real retention/access policy would be
defined together with the department, not decided by us alone.

**Q14. What's your actual evidence this works?**
119 automated backend tests, covering every rule's PASS/FAIL/NEEDS VERIFICATION paths and a
full 12-label end-to-end run. More honestly telling: this build cycle we repeatedly re-scanned
**real product photos** (not the synthetic demo set), found real extraction bugs from the
actual OCR output, traced each one to its root cause, fixed it, and locked the fix in with a
test. That visible trail — find a real bug, fix it, verify against the real photo again — is
itself part of the evidence. We're not claiming a polished, bug-free system; we're showing one
that gets real bugs found and fixed against real inputs, which is a more credible claim.

**Q15. What would this cost to run nationally?**
No full national cost model yet — building one responsibly needs real per-state volume numbers
we don't have. What we can say confidently: the cost per scan is near zero (no AI-API billing —
Tesseract and the rule engine are both free and self-hosted), so total cost scales mainly with
hosting (compute + storage + database) — a much smaller, more predictable number than any
per-transaction-billed alternative at national scale.

**Q16. What about exempted categories (small packs, restaurant food, etc.)?**
Honestly, not automatic yet — a real, named gap (§1, §3), not hidden. The exemptions (small
packs under 10g/10ml, restaurant food, certain drug formulations, farm produce over 50kg, pan
masala) are documented but not yet checked against a scanned package automatically. The fix:
an exemptions lookup based on declared size and category, shown to the inspector to confirm
rather than silently applied — since wrongly treating a non-exempt package as exempt would be
the worse mistake. Clearly scoped, just not built yet.

**Q17. Does this work offline, in poor-connectivity areas?**
Not today — it's a web app that needs a connection to the backend to process a scan. The
OCR/rule engine itself has no external API dependency (Tesseract runs locally), so an offline
or local-network version is architecturally possible later, just not something we've built or
tested.

**Q18. Who resolves a NEEDS VERIFICATION result?**
Today: the human Inspector, using the evidence shown alongside it (the extracted text, the
cropped photo region, confidence, and why it wasn't auto-resolved). There's no built-in way yet
to mark one as "manually confirmed" inside the tool — a sensible next feature, not built yet.

**Q19. Why should DoCA trust an automated report over a trained Inspector's own judgement?**
It shouldn't have to pick one — that's the wrong question, and we say so directly. The tool
isn't asking to be trusted instead of the Inspector; every report is built to be evidence *for*
the Inspector's judgement, with full traceability (exact location, confidence, clause cited),
specifically so the Inspector — not the software — is still the one making the call.

**Q20. What's the biggest risk in this project right now?**
Honestly: the reliability of the current free-tier hosting, not the compliance logic itself.
The rule engine and extraction pipeline have been stress-tested against real photos this build
cycle; the free hosting used for the hackathon demo (cold starts, storage wiped on restart) is
the weaker link, and clearly not what a real pilot would run on.

**Q21. Why Python/FastAPI instead of something else?**
FastAPI gives fast, well-typed API development with automatic documentation, and Python has by
far the most mature free OCR/image tooling (OpenCV, pytesseract) — directly serving the
offline-first, no-per-call-cost goal from Q8.

**Q22. What would you do differently if you started over?**
Define the real-world accuracy test — a labelled set of real, varied field photos, not
synthetic mockups — *before* writing the rule engine, not after. The most valuable work this
build cycle was finding and fixing real OCR bugs from real photos, late in the process; doing
that systematically from day one would have caught the same issues earlier and cheaper.

**Q23. Does it correctly say PASS for a genuinely compliant product?**
Yes — the demo set includes labels built to be fully compliant, and the rule engine correctly
returns PASS across every applicable check for them. A tool that only ever finds problems and
never confirms compliance would itself be a red flag; this one does both, visibly, in the same
report either way.

**Q24. There's a compliance_score number — how does that relate to the PASS/FAIL list?**
The itemised list is always the real answer. The score (pass count ÷ applicable checks) is
shown only as a secondary summary, clearly labelled, never as a stand-in for actually reading
the findings — a deliberate choice so a single number can't replace the real evidence.

**Q25. In a real deployment, who would actually have dashboard (admin) access?**
The supervising Controller/Deputy Controller tier, for the targeting use case in §3 — while
Inspectors do the scanning in the field. That maps directly onto the real three-tier structure
of Legal Metrology enforcement (§1), not an arbitrary split we invented.

---

### 6. The pitch, and a 60-second demo script

**One paragraph:**

> Legal Metrology inspectors in India check mandatory declarations — manufacturer identity,
> net quantity, MRP, dates, consumer care, country of origin, font size, and placement — on
> every packaged product sold in the country, with a field workforce that's clearly far smaller
> than the number of products it needs to cover. The LMPC Compliance Scanner turns that manual,
> page-by-page check into a photograph: an Inspector uploads a picture of a package and gets
> back, in seconds, an itemised report where every finding — pass, fail, or "needs a human
> look" — is tied to the exact clause of the Legal Metrology (Packaged Commodities) Rules,
> 2011, with the extracted text, where it was found, and how confident the OCR was. It reads
> English, Hindi, and Gujarati, because that's what Indian shelves actually carry. It never
> asserts a confident wrong answer — where the evidence is weak, it says so, because a
> compliance tool that fakes certainty is more dangerous than one that admits doubt. And
> because it runs on free, offline OCR instead of a paid AI API, it costs nothing per scan to
> run at any scale a state department needs.

**60-second demo script:**

- **[0-10s]** "This is a real photo of a real product — not a mockup." Upload it live.
- **[10-20s]** While it processes: "It reads the label in whatever script it's actually printed
  in, pulls out every mandatory declaration, and checks it against specific clauses of the
  Rules."
- **[20-40s]** Report appears. Point at one PASS ("manufacturer address, found, here's the exact
  spot it came from") and one FAIL or NEEDS VERIFICATION ("MRP is there, but missing the
  'inclusive of all taxes' wording — FAIL" or "font size — this is a relative signal only,
  here's why, and here's how a real measurement would make it a hard check").
- **[40-50s]** Scroll to the annotated photo: "Every finding is marked directly on the image,
  not just listed in a table."
- **[50-60s]** Close on the dashboard: "And every scan becomes part of a permanent, searchable
  record — which manual inspection has never had."

---

## A note on how this document was written

Every factual claim here that came from outside our own codebase (penalty amounts, the
three-tier enforcement structure, the consumer-helpline process, exemption thresholds, the
e-commerce rules) was checked against a live web search and is cited inline above. We looked
specifically for a national inspector count and a national product count, found neither
published anywhere, and said so instead of inventing a number to make a slide look tidier —
the same "don't fabricate" rule this whole project runs on, just applied to market numbers too.
