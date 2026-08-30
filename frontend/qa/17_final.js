const { chromium } = require('playwright');
const BASE='http://127.0.0.1:5173';
(async()=>{
 const b=await chromium.launch();
 // mobile nav open
 const m=await b.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
 const mp=await m.newPage();
 await mp.goto(BASE,{waitUntil:'networkidle'}); await mp.waitForTimeout(1500);
 await mp.click('.hero-burger'); await mp.waitForTimeout(900);
 console.log('mobile nav:', JSON.stringify(await mp.evaluate(()=>({
   expanded:document.querySelector('.hero-burger').getAttribute('aria-expanded'),
   sheetOpen:document.querySelector('.hero-sheet').classList.contains('open'),
   linkOpacity:getComputedStyle(document.querySelector('.hero-sheet a')).opacity,
   overflowX:document.documentElement.scrollWidth>390,
 }))));
 await mp.screenshot({path:'shots/17_mobile_nav.png'});
 await m.close();
 // light theme hero
 const l=await b.newContext({viewport:{width:1280,height:720}});
 await l.addInitScript(()=>{try{localStorage.setItem('lmpc-theme','light')}catch(e){}});
 const lp=await l.newPage();
 await lp.goto(BASE,{waitUntil:'networkidle'}); await lp.waitForTimeout(2500);
 await lp.screenshot({path:'shots/17_hero_light.png'});
 console.log('light theme:', JSON.stringify(await lp.evaluate(()=>({
   theme:document.documentElement.getAttribute('data-theme'),
   heroBg:getComputedStyle(document.querySelector('.hero-stage')).backgroundColor,
   videoPlaying:!document.querySelector('.hero-video').paused,
 }))));
 await l.close();
 await b.close();
})();
