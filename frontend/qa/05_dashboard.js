const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5173';

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: 'admin_state.json' });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/dashboard`);
  await page.waitForTimeout(700);
  await page.screenshot({ path: 'shots/05_dashboard_after_11_scans.png', fullPage: true });

  const total = await page.locator('.stat-tile .stat-value').nth(0).textContent();
  const pass = await page.locator('.stat-tile .stat-value').nth(1).textContent();
  const fail = await page.locator('.stat-tile .stat-value').nth(2).textContent();
  const verify = await page.locator('.stat-tile .stat-value').nth(3).textContent();
  const noncompliantRows = await page.locator('.results-table').last().locator('tbody tr').count();
  const noncompliantNames = await page.locator('.results-table').last().locator('tbody tr td:first-child').allTextContents();

  console.log(JSON.stringify({ total, pass, fail, verify, noncompliantRows, noncompliantNames }, null, 2));
  await browser.close();
})();
