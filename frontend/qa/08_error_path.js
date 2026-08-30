const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5173';

async function tryUpload(page, filename, tag) {
  await page.goto(`${BASE}/scan`);
  await page.setInputFiles('input[type=file]', filename);
  await page.fill('input[placeholder*="Fresh Valley"]', `Error path test - ${tag}`);
  await page.click('button[type=submit]');
  try {
    await page.waitForURL('**/scans/**', { timeout: 20000 });
    await page.waitForTimeout(800);
    await page.screenshot({ path: `shots/08_${tag}_scan_detail.png`, fullPage: true });
    console.log(tag, '-> succeeded, went to', page.url());
  } catch (e) {
    await page.waitForTimeout(500);
    await page.screenshot({ path: `shots/08_${tag}_error_state.png`, fullPage: true });
    const bodyText = await page.locator('body').innerText();
    console.log(tag, '-> did not navigate. Page text snippet:', bodyText.slice(0, 500));
  }
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: 'inspector_state.json' });
  const page = await ctx.newPage();

  await tryUpload(page, 'blank_white.png', 'blank_white');
  await tryUpload(page, 'noise.png', 'noise');

  await browser.close();
})();
