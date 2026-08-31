const { chromium } = require('playwright');
const BASE='http://127.0.0.1:5173';
(async()=>{
 const b=await chromium.launch();
 const p=await b.newPage();
 p.setViewportSize && await p.setViewportSize({width:1280,height:720});
 const errs=[]; p.on('pageerror',e=>errs.push(e.message));
 await p.goto(BASE,{waitUntil:'networkidle'});
 await p.waitForTimeout(2500);
 await p.screenshot({path:'shots/18_hero_typography.png'});
 const font = await p.evaluate(()=>getComputedStyle(document.querySelector('.hero-title')).fontFamily);
 console.log('hero title font:', font);
 await p.evaluate(()=>document.querySelector('#how')?.scrollIntoView({block:'start'}));
 await p.waitForTimeout(800);
 await p.screenshot({path:'shots/18_landing_body.png'});
 console.log('errors:', errs.length?errs:'none');
 await b.close();
})();
