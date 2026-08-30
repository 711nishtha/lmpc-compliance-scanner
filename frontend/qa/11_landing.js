const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5173';
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle','--enable-gpu'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));

  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3500);
  await page.screenshot({ path: 'shots/11_landing_hero.png' });

  // canvas actually rendering?
  const canvasInfo = await page.evaluate(() => {
    const c = document.querySelector('canvas');
    if (!c) return { present: false };
    const ctx2 = c.getContext('webgl2') || c.getContext('webgl');
    return { present: true, w: c.width, h: c.height, gl: !!ctx2 };
  });
  console.log('canvas:', JSON.stringify(canvasInfo));

  // measure real FPS over 3s
  const fps = await page.evaluate(() => new Promise(res => {
    let f = 0; const t0 = performance.now();
    (function loop(){ f++; performance.now() - t0 < 3000 ? requestAnimationFrame(loop) : res(+(f/((performance.now()-t0)/1000)).toFixed(1)); })();
  }));
  console.log('measured FPS:', fps);

  // scroll through and capture each section
  const sections = ['landing-band','landing-steps','landing-band-alt','landing-honesty','landing-final'];
  for (let i=0;i<sections.length;i++){
    await page.evaluate(s => document.querySelector('.'+s)?.scrollIntoView({behavior:'instant',block:'center'}), sections[i]);
    await page.waitForTimeout(900);
    await page.screenshot({ path: `shots/11_landing_${i+2}_${sections[i]}.png` });
  }
  await page.screenshot({ path: 'shots/11_landing_full.png', fullPage: true });

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log('horizontal overflow:', overflow);
  console.log('errors:', errs.length ? errs.slice(0,5) : 'none');
  await browser.close();
})();
