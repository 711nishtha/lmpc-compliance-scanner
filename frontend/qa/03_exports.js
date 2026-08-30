const { chromium } = require('playwright');

const BASE = 'http://127.0.0.1:5173';

async function downloadBoth(page, scanId, tag) {
  await page.goto(`${BASE}/scans/${scanId}`);
  await page.waitForTimeout(800);

  const [pdfDownload] = await Promise.all([
    page.waitForEvent('download'),
    page.click('text=Download PDF report'),
  ]);
  await pdfDownload.saveAs(`downloads/${tag}_scan${scanId}.pdf`);

  const [docxDownload] = await Promise.all([
    page.waitForEvent('download'),
    page.click('text=Download editable DOCX'),
  ]);
  await docxDownload.saveAs(`downloads/${tag}_scan${scanId}.docx`);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: 'inspector_state.json', acceptDownloads: true });
  const page = await ctx.newPage();

  // scan 1 = fully_compliant (PASS-heavy), scan 2 = missing_mrp (FAIL present)
  await downloadBoth(page, 1, 'pass_heavy');
  await downloadBoth(page, 2, 'fail_heavy');

  await browser.close();
  console.log('done');
})();
