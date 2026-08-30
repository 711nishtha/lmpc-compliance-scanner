const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5173';

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: 'inspector_state.json', viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();

  await page.goto(`${BASE}/scan`);
  await page.waitForTimeout(300);
  await page.screenshot({ path: 'shots/06_00_projector_scan_page.png' });

  await page.goto(`${BASE}/scans/1`);
  await page.waitForTimeout(900);
  await page.screenshot({ path: 'shots/06_01_projector_scan_detail_viewport_only.png' }); // NOT fullPage -- what's actually visible without scrolling
  await page.screenshot({ path: 'shots/06_02_projector_scan_detail_fullpage.png', fullPage: true });

  await page.goto(`${BASE}/repository`);
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'shots/06_03_projector_repository.png' });

  const adminCtx = await browser.newContext({ storageState: 'admin_state.json', viewport: { width: 1280, height: 720 } });
  const adminPage = await adminCtx.newPage();
  await adminPage.goto(`${BASE}/dashboard`);
  await adminPage.waitForTimeout(500);
  await adminPage.screenshot({ path: 'shots/06_04_projector_dashboard.png' });

  await browser.close();
  console.log('done');
})();
