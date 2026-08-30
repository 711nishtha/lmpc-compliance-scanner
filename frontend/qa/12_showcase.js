/* Verifies the "See it scan" showcase: typewriter, scrub mechanic, pills, mobile fallback, FPS. */
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5173';

(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--enable-gpu'] });

  // ---------- desktop: scrub mode ----------
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));

  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);

  // FPS while the 3D hero is on screen AND the showcase has mounted below it
  const heroFps = await page.evaluate(() => new Promise(res => {
    let f = 0; const t0 = performance.now();
    (function l(){ f++; performance.now()-t0 < 3000 ? requestAnimationFrame(l) : res(+(f/((performance.now()-t0)/1000)).toFixed(1)); })();
  }));
  console.log('FPS (hero + showcase mounted):', heroFps);

  await page.evaluate(() => document.querySelector('#see-it-scan')?.scrollIntoView({ behavior: 'instant', block: 'start' }));
  await page.waitForTimeout(1200);
  await page.screenshot({ path: 'shots/12_showcase_typing.png' });

  // let the typewriter finish
  await page.waitForTimeout(2600);
  await page.screenshot({ path: 'shots/12_showcase_done.png' });

  const info = await page.evaluate(() => {
    const v = document.querySelector('.scrub-video');
    const h = document.querySelector('.typewriter-line [aria-hidden="true"]');
    return {
      videoPresent: !!v,
      duration: v ? +v.duration.toFixed(2) : null,
      readyState: v ? v.readyState : null,
      currentTime: v ? +v.currentTime.toFixed(3) : null,
      paused: v ? v.paused : null,
      typed: h ? h.textContent.trim() : null,
      cursorPresent: !!document.querySelector('.typewriter-cursor'),
      pills: [...document.querySelectorAll('.scan-pill')].map(p => p.textContent.trim()),
      hint: document.querySelector('.scrub-hint')?.textContent?.trim() || null,
    };
  });
  console.log('desktop:', JSON.stringify(info, null, 2));

  // ---------- exercise the scrub ----------
  await page.mouse.move(200, 400);
  for (let x = 200; x <= 1100; x += 45) { await page.mouse.move(x, 400); await page.waitForTimeout(45); }
  await page.waitForTimeout(700);
  const after = await page.evaluate(() => +document.querySelector('.scrub-video').currentTime.toFixed(3));
  console.log('currentTime after rightward scrub:', after, after > 0.2 ? '-> SCRUB WORKS' : '-> SCRUB DID NOT MOVE');
  await page.screenshot({ path: 'shots/12_showcase_scrubbed.png' });

  // scrub back left
  for (let x = 1100; x >= 250; x -= 60) { await page.mouse.move(x, 400); await page.waitForTimeout(35); }
  await page.waitForTimeout(600);
  const back = await page.evaluate(() => +document.querySelector('.scrub-video').currentTime.toFixed(3));
  console.log('currentTime after leftward scrub:', back, back < after ? '-> REVERSE WORKS' : '-> REVERSE FAILED');

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log('horizontal overflow:', overflow);
  console.log('console errors:', errs.length ? errs.slice(0, 5) : 'none');
  await ctx.close();

  // ---------- mobile: autoplay fallback ----------
  const m = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true, isMobile: true,
  });
  const mp = await m.newPage();
  await mp.goto(BASE, { waitUntil: 'networkidle' });
  await mp.evaluate(() => document.querySelector('#see-it-scan')?.scrollIntoView({ behavior: 'instant', block: 'start' }));
  await mp.waitForTimeout(3000);
  const mobile = await mp.evaluate(() => {
    const v = document.querySelector('.scrub-video');
    return v ? { paused: v.paused, loop: v.loop, currentTime: +v.currentTime.toFixed(2) } : null;
  });
  console.log('mobile fallback:', JSON.stringify(mobile),
    mobile && !mobile.paused && mobile.currentTime > 0 ? '-> AUTOPLAY WORKS' : '-> NOT PLAYING');
  await mp.screenshot({ path: 'shots/12_showcase_mobile.png' });
  const mOverflow = await mp.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log('mobile horizontal overflow:', mOverflow);

  await browser.close();
})();
