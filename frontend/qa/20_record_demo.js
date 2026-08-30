/* Records REAL footage of the live scan flow for the landing page's "See it scan" section.
 *
 * Not a mockup and not a screen-capture hack: this drives the actual running app through
 * Playwright's built-in recordVideo, uploading real demo labels and waiting for the real
 * annotated image + itemised checklist to render.
 *
 * Flow: demo label 01 (fully compliant) -> its report -> demo label 12 (placement violation)
 * -> its report. Back to back in one continuous session.
 *
 * Requires: backend + frontend running, and inspector_state.json from 01_auth.js.
 * Output: recordings/<hash>.webm  (converted to mp4 by 21_encode_demo.sh)
 */
const { chromium } = require('playwright');
const path = require('path');

const BASE = 'http://127.0.0.1:5173';
const DEMO_DIR = 'd:/Projects/sih26034/demo_data';

// 1280x720 keeps the recording at projector aspect and avoids a huge encode.
const VIEW = { width: 1280, height: 720 };

async function scanOne(page, file, productName, opts = {}) {
  await page.goto(`${BASE}/scan`);
  await page.waitForTimeout(700);

  await page.setInputFiles('input[type=file]', path.join(DEMO_DIR, file));
  await page.waitForTimeout(500); // let the preview thumbnail paint

  // Type the product name visibly rather than fill() — it reads as real usage on video.
  await page.click('input[placeholder*="Fresh Valley"]');
  await page.type('input[placeholder*="Fresh Valley"]', productName, { delay: 28 });
  await page.waitForTimeout(350);

  await page.click('button[type=submit]');
  // The "Scanning…" state is part of the story — let it be visible.
  await page.waitForURL('**/scans/**', { timeout: 45000 });

  // Wait for the annotated image to actually be decoded, not just present in the DOM.
  await page.waitForSelector('.annotated-image', { timeout: 20000 });
  await page.waitForFunction(() => {
    const img = document.querySelector('.annotated-image');
    return img && img.complete && img.naturalWidth > 0;
  }, { timeout: 20000 });
  await page.waitForTimeout(900);

  // Scroll the itemised checklist into view so the citations are on screen.
  await page.evaluate(() => {
    const t = document.querySelector('.results-table');
    if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  await page.waitForTimeout(opts.dwell ?? 1800);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    storageState: 'inspector_state.json',
    viewport: VIEW,
    recordVideo: { dir: 'recordings', size: VIEW },
  });
  const page = await ctx.newPage();

  await scanOne(page, '01_fully_compliant.png', 'Fresh Valley Snacks 200g', { dwell: 2000 });
  await scanOne(page, '12_mrp_placed_far_from_group.png', 'Value Deal Detergent 500g', { dwell: 2200 });

  const video = page.video();
  await ctx.close(); // must close the context for the video to be finalised
  const p = await video.path();
  console.log('recorded:', p);
  await browser.close();
})();
