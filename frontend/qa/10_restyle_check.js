const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5173';
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: 'inspector_state.json', viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });

  await page.goto(`${BASE}/scan`); await page.waitForTimeout(1200);
  await page.screenshot({ path: 'shots/10_scan.png' });

  await page.goto(`${BASE}/scans/1`); await page.waitForTimeout(1500);
  await page.screenshot({ path: 'shots/10_report_viewport.png' });
  await page.screenshot({ path: 'shots/10_report_full.png', fullPage: true });

  await page.goto(`${BASE}/repository`); await page.waitForTimeout(900);
  await page.screenshot({ path: 'shots/10_repository.png' });

  const admin = await browser.newContext({ storageState: 'admin_state.json', viewport: { width: 1280, height: 720 } });
  const ap = await admin.newPage();
  await ap.goto(`${BASE}/dashboard`); await ap.waitForTimeout(900);
  await ap.screenshot({ path: 'shots/10_dashboard.png' });

  // horizontal overflow check at projector res
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log('horizontal overflow at 1280x720:', overflow);
  console.log('console errors:', errs.length ? errs : 'none');
  await browser.close();
})();
