const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5173';

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: 'inspector_state.json' });
  const page = await ctx.newPage();

  // Baseline: all 11 scans
  await page.goto(`${BASE}/repository`);
  await page.waitForTimeout(600);
  await page.screenshot({ path: 'shots/04_00_repository_all.png', fullPage: true });
  const allRows = await page.locator('.results-table tbody tr').count();

  // Search by product name
  await page.fill('input[placeholder*="Search"]', 'Golden Crunch');
  await page.click('text=Search');
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'shots/04_01_repository_search_golden.png', fullPage: true });
  const searchRows = await page.locator('.results-table tbody tr').count();
  const searchTexts = await page.locator('.results-table tbody tr td:first-child').allTextContents();

  // Reset, filter by status FAIL
  await page.fill('input[placeholder*="Search"]', '');
  await page.selectOption('select >> nth=0', 'FAIL');
  await page.click('text=Search');
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'shots/04_02_repository_filter_fail.png', fullPage: true });
  const failRows = await page.locator('.results-table tbody tr').count();
  const failStatuses = await page.locator('.results-table tbody tr td:nth-child(2)').allTextContents();

  // Reset status, filter by date range (today only, should include all; then a future date range that excludes all)
  await page.selectOption('select >> nth=0', '');
  const today = new Date().toISOString().slice(0, 10);
  await page.fill('input[type=date] >> nth=0', today);
  await page.fill('input[type=date] >> nth=1', today);
  await page.click('text=Search');
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'shots/04_03_repository_filter_date_today.png', fullPage: true });
  const dateRows = await page.locator('.results-table tbody tr').count();

  // Date range that excludes everything (far future)
  await page.fill('input[type=date] >> nth=0', '2099-01-01');
  await page.fill('input[type=date] >> nth=1', '2099-01-02');
  await page.click('text=Search');
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'shots/04_04_repository_filter_date_future_empty.png', fullPage: true });
  const futureRows = await page.locator('.results-table tbody tr').count();

  console.log(JSON.stringify({ allRows, searchRows, searchTexts, failRows, failStatuses, dateRows, futureRows }, null, 2));
  await browser.close();
})();
