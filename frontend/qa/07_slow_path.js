const { chromium } = require('playwright');
const path = require('path');
const BASE = 'http://127.0.0.1:5173';
const DEMO_DIR = 'd:/Projects/sih26034/demo_data';

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: 'inspector_state.json' });
  const page = await ctx.newPage();

  // Delay the /api/scans POST response by 6s to simulate slow OCR
  await page.route('**/api/scans', async (route) => {
    if (route.request().method() === 'POST') {
      await new Promise((r) => setTimeout(r, 6000));
    }
    await route.continue();
  });

  await page.goto(`${BASE}/scan`);
  await page.setInputFiles('input[type=file]', path.join(DEMO_DIR, '02_missing_mrp.png'));
  await page.fill('input[placeholder*="Fresh Valley"]', 'Slow Path Test Product');
  await page.click('button[type=submit]');

  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'shots/07_00a_mid_wait_1s.png' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'shots/07_00b_mid_wait_3s.png' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'shots/07_00c_mid_wait_5s.png' });

  await page.waitForURL('**/scans/**', { timeout: 15000 });
  await page.screenshot({ path: 'shots/07_01_after_slow_scan_resolved.png' });
  console.log('resolved to', page.url());

  await browser.close();
})();
