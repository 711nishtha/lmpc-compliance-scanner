/* Full QA in BOTH themes: landing + app screens, FPS with ambient video + floaters active,
 * projector resolution, overflow, console errors, and the mobile nav interaction. */
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5173';
const PROJECTOR = { width: 1280, height: 720 };

async function withTheme(browser, theme, storageState) {
  const ctx = await browser.newContext({
    viewport: PROJECTOR,
    ...(storageState ? { storageState } : {}),
  });
  // Seed the choice before any page script runs, so the pre-paint script picks it up.
  await ctx.addInitScript((t) => {
    try { localStorage.setItem('lmpc-theme', t); } catch (e) {}
  }, theme);
  return ctx;
}

(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--enable-gpu'] });

  for (const theme of ['light', 'dark']) {
    console.log(`\n================ ${theme.toUpperCase()} ================`);
    const ctx = await withTheme(browser, theme);
    const page = await ctx.newPage();
    const errs = [];
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));

    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2600);

    const applied = await page.evaluate(() => ({
      theme: document.documentElement.getAttribute('data-theme'),
      bg: getComputedStyle(document.body).backgroundColor,
      heroBg: getComputedStyle(document.querySelector('.landing-hero')).backgroundColor,
      ambient: !!document.querySelector('.ambient-video'),
      ambientPlaying: (() => { const v = document.querySelector('.ambient-video'); return v ? !v.paused : null; })(),
      floaters: document.querySelectorAll('.floater').length,
      displayFont: getComputedStyle(document.querySelector('h1')).fontFamily,
      bodyFont: getComputedStyle(document.body).fontFamily,
    }));
    console.log('applied:', JSON.stringify(applied));

    // FPS with 3D scene + ambient video + floating objects ALL active.
    const fps = await page.evaluate(() => new Promise(res => {
      let f = 0; const t0 = performance.now();
      (function l(){ f++; performance.now()-t0 < 4000 ? requestAnimationFrame(l)
        : res(+(f/((performance.now()-t0)/1000)).toFixed(1)); })();
    }));
    console.log(`FPS (3D + ambient video + floaters): ${fps}`);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    console.log('horizontal overflow:', overflow);
    await page.screenshot({ path: `shots/13_landing_${theme}.png` });

    // Status badge colours as actually rendered, for the contrast record.
    await page.evaluate(() => document.querySelector('#see-it-scan')?.scrollIntoView({ block: 'start' }));
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `shots/13_showcase_${theme}.png` });

    console.log('console errors:', errs.length ? errs.slice(0, 4) : 'none');
    await ctx.close();

    // ---- app screen in the same theme ----
    const actx = await withTheme(browser, theme, 'inspector_state.json');
    const ap = await actx.newPage();
    await ap.goto(`${BASE}/scans/1`, { waitUntil: 'networkidle' });
    await ap.waitForTimeout(1800);
    const badges = await ap.evaluate(() => {
      const out = {};
      document.querySelectorAll('.badge').forEach(b => {
        const cs = getComputedStyle(b);
        const cls = [...b.classList].find(c => c.startsWith('status-'));
        if (cls && !out[cls]) out[cls] = { bg: cs.backgroundColor, fg: cs.color, glyph: getComputedStyle(b, '::before').content };
      });
      return out;
    });
    console.log('rendered badges:', JSON.stringify(badges, null, 1));
    await ap.screenshot({ path: `shots/13_scandetail_${theme}.png` });
    await actx.close();
  }

  // ---- mobile nav interaction (dark) ----
  console.log('\n================ MOBILE NAV ================');
  const mctx = await withTheme(browser, 'dark');
  await mctx.addInitScript(() => {});
  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  await m.addInitScript(() => { try { localStorage.setItem('lmpc-theme', 'dark'); } catch(e){} });
  const mp = await m.newPage();
  await mp.goto(BASE, { waitUntil: 'networkidle' });
  await mp.waitForTimeout(1500);
  await mp.click('.nav-burger');
  await mp.waitForTimeout(900);
  const navState = await mp.evaluate(() => ({
    expanded: document.querySelector('.nav-burger').getAttribute('aria-expanded'),
    sheetOpen: document.querySelector('.nav-sheet').classList.contains('open'),
    overlayOpen: document.querySelector('.nav-overlay').classList.contains('open'),
    linkOpacity: getComputedStyle(document.querySelector('.nav-sheet a')).opacity,
  }));
  console.log('nav open:', JSON.stringify(navState));
  await mp.screenshot({ path: 'shots/13_mobile_nav_open.png' });
  await mp.keyboard.press('Escape');
  await mp.waitForTimeout(700);
  console.log('after Escape, expanded:', await mp.evaluate(() => document.querySelector('.nav-burger').getAttribute('aria-expanded')));
  await m.close(); await mctx.close();
  await browser.close();
})();
