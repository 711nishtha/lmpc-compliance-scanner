# Demo Data — Synthetic Mock Labels

Plain, clearly fictional labels built to exercise specific Legal Metrology rule checks in a controlled, repeatable demo walkthrough. None depict real branded products (see docs/LEGAL_REQUIREMENTS.md Step 8 IP note).

| File | Exercises | Description |
|---|---|---|
| 01_fully_compliant.png | R6-1, R6-3, R6-4, R6-5, R6-7, R6-9, R8-1, R8-2 | All Rule 6 declarations present, MRP tax-inclusive, complete consumer care. |
| 02_missing_mrp.png | R6-7, R8-2 | Constructed to violate R6-7 (Rule 6(1)(e)) — no MRP declared anywhere on label. |
| 03_undersized_mrp_font.png | R7-1, R8-2 | Constructed to exercise the Rule 7 Tier-1 relative font-size signal — MRP text rendered much smaller than the brand name. |
| 04_missing_consumer_care.png | R6-9, R8-2 | Constructed to violate R6-9 (Rule 6(2)) — no consumer care details at all. |
| 05_wrong_unit_liquid_as_pieces.png | R6-4, R8-2 | Constructed to violate R6-4 (Rule 6(1)(c)) — a liquid commodity with net quantity declared in a count unit instead of volume. |
| 06_missing_mfg_date.png | R6-5, R8-2 | Constructed to violate R6-5 (Rule 6(1)(d)) — no month/year of manufacture. |
| 07_imported_missing_country_of_origin.png | R6-2, R8-2 | Constructed to violate R6-2 (Rule 6(1)(aa)) — imported product with no country-of-origin declaration. |
| 08_missing_manufacturer.png | R6-1, R8-2 | Constructed to violate R6-1 (Rule 6(1)(a)) — no manufacturer/packer/importer name or address. |
| 09_hindi_manufacturer_bilingual.png | R6-1, R6-3, R6-4, R6-5, R6-7, R6-9, R8-1, R8-2 | Real Devanagari (Hindi) script — manufacturer and consumer-care lines in Hindi, net quantity/MRP/mfg date in English with Arabic numerals (standard Indian retail label convention). Fully compliant; exercises real-script OCR + anchor matching, not just the digit-normalization unit test. |
| 10_gujarati_bilingual_liquid.png | R6-1, R6-3, R6-4, R6-5, R6-7, R6-9, R8-1, R8-2 | Real Gujarati script — net quantity, MRP and consumer-care lines in Gujarati (with Arabic numerals, as standard on real Indian packaging even on vernacular labels). Fully compliant liquid commodity. |
| 11_hindi_gujarati_imported_missing_coo.png | R6-1, R6-2, R6-3, R6-4, R6-5, R6-7, R6-9, R8-2 | Mixed Hindi + Gujarati script, imported product missing country of origin (violates R6-2). Net quantity line uses a genuine Devanagari numeral (८०, not OCR-misrecognition-induced) to verify digit normalization on real native-script digits, not just corrupted Latin ones. Consumer care given in Gujarati with phone only (no email) to exercise the partial-fields NEEDS_VERIFICATION path (R6-9) on real script. |
| 12_mrp_placed_far_from_group.png | R6-1, R6-3, R6-4, R6-5, R6-7, R6-9, R8-1 | Constructed to violate R8-1 (Rule 2(h) + Rule 8(1)) — MRP is placed in an isolated corner of the image, far from where every other Rule 6 declaration is grouped, simulating a declaration printed on a different panel of the package instead of the principal display panel with the rest. |