const { chromium } = require('playwright');
const path = require('path');

const BASE = 'http://127.0.0.1:5173';
const DEMO_DIR = 'd:/Projects/sih26034/demo_data';

const LABELS = [
  { file: '01_fully_compliant.png', name: 'Fresh Valley Snacks 200g', imported: '' },
  { file: '02_missing_mrp.png', name: 'Golden Crunch Biscuits 100g', imported: '' },
  { file: '03_undersized_mrp_font.png', name: 'Royal Spice Masala 50g', imported: '' },
  { file: '04_missing_consumer_care.png', name: 'Sunrise Cooking Oil 1L', imported: '' },
  { file: '05_wrong_unit_liquid_as_pieces.png', name: 'Clearwater Drinking Water', imported: '' },
  { file: '06_missing_mfg_date.png', name: 'Mountain Herbal Tea 100g', imported: '' },
  { file: '07_imported_missing_country_of_origin.png', name: 'Alpine Chocolate Bar 80g', imported: 'yes' },
  { file: '08_missing_manufacturer.png', name: 'Value Pack Rice 5kg', imported: '' },
  { file: '09_hindi_manufacturer_bilingual.png', name: 'Mountain Herbal Chai 100g', imported: '' },
  { file: '10_gujarati_bilingual_liquid.png', name: 'Sunrise Cooking Oil Gujarati 1L', imported: '' },
  { file: '11_hindi_gujarati_imported_missing_coo.png', name: 'Alpine Chocolate Bar Mixed Script 80g', imported: 'yes' },
  { file: '12_mrp_placed_far_from_group.png', name: 'Value Deal Detergent Powder 500g', imported: '' },
];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: 'inspector_state.json' });
  const page = await ctx.newPage();

  const results = [];
  for (let i = 0; i < LABELS.length; i++) {
    const label = LABELS[i];
    const n = String(i + 1).padStart(2, '0');
    await page.goto(`${BASE}/scan`);
    await page.setInputFiles('input[type=file]', path.join(DEMO_DIR, label.file));
    await page.fill('input[placeholder*="Fresh Valley"]', label.name);
    if (label.imported) {
      await page.selectOption('select >> nth=1', label.imported);
    }
    await page.screenshot({ path: `shots/02_${n}_scan_form_filled.png` });

    const submitStart = Date.now();
    await page.click('button[type=submit]');
    // capture loading state quickly
    await page.waitForTimeout(150);
    try {
      await page.screenshot({ path: `shots/02_${n}_loading_state.png` });
    } catch (e) { /* ignore */ }

    try {
      await page.waitForURL('**/scans/**', { timeout: 30000 });
      const elapsed = Date.now() - submitStart;
      await page.waitForTimeout(800); // let annotated image fetch resolve
      await page.screenshot({ path: `shots/02_${n}_scan_detail.png`, fullPage: true });
      const url = page.url();
      results.push({ file: label.file, ok: true, url, elapsedMs: elapsed });
    } catch (e) {
      await page.screenshot({ path: `shots/02_${n}_ERROR.png`, fullPage: true });
      results.push({ file: label.file, ok: false, error: e.message });
    }
  }

  console.log(JSON.stringify(results, null, 2));
  await browser.close();
})();
