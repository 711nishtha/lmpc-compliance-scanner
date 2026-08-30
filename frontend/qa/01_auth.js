const { chromium } = require('playwright');

const BASE = 'http://127.0.0.1:5173';

async function registerAndLogin(page, email, password, role, shotPrefix) {
  await page.goto(`${BASE}/login`);
  await page.click('text=Need an account? Register');
  await page.fill('input[type=email]', email);
  await page.fill('input[type=password]', password);
  await page.selectOption('select', role);
  await page.screenshot({ path: `shots/${shotPrefix}_register_form.png` });
  await page.click('button[type=submit]');
  await page.waitForURL('**/scan');
  await page.screenshot({ path: `shots/${shotPrefix}_after_login_scan_page.png`, fullPage: true });
}

(async () => {
  const browser = await chromium.launch();

  // Inspector
  const inspectorCtx = await browser.newContext();
  const inspectorPage = await inspectorCtx.newPage();
  await registerAndLogin(inspectorPage, 'inspector1@example.com', 'password123', 'inspector', '01a_inspector');
  await inspectorPage.goto(`${BASE}/dashboard`);
  await inspectorPage.waitForTimeout(500);
  await inspectorPage.screenshot({ path: 'shots/01a_inspector_dashboard.png', fullPage: true });
  await inspectorPage.goto(`${BASE}/repository`);
  await inspectorPage.waitForTimeout(500);
  await inspectorPage.screenshot({ path: 'shots/01a_inspector_repository.png', fullPage: true });
  await inspectorCtx.storageState({ path: 'inspector_state.json' });
  await inspectorCtx.close();

  // Admin
  const adminCtx = await browser.newContext();
  const adminPage = await adminCtx.newPage();
  await registerAndLogin(adminPage, 'admin1@example.com', 'password123', 'admin', '01b_admin');
  await adminPage.goto(`${BASE}/dashboard`);
  await adminPage.waitForTimeout(500);
  await adminPage.screenshot({ path: 'shots/01b_admin_dashboard.png', fullPage: true });
  await adminPage.goto(`${BASE}/repository`);
  await adminPage.waitForTimeout(500);
  await adminPage.screenshot({ path: 'shots/01b_admin_repository.png', fullPage: true });
  await adminCtx.storageState({ path: 'admin_state.json' });
  await adminCtx.close();

  await browser.close();
  console.log('done');
})();
