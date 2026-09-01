const { chromium } = require('playwright');
const BASE='http://localhost:5173';
(async()=>{
 const b=await chromium.launch();
 // --- responsive
 for(const [w,h,name] of [[390,844,'mobile'],[834,1112,'tablet'],[1920,1080,'wide']]){
  const ctx=await b.newContext({viewport:{width:w,height:h},storageState:'admin_state.json'});
  const p=await ctx.newPage();
  for(const [route,tag] of [['/dashboard','dash'],['/scan','scan'],['/repository','repo']]){
   await p.goto(BASE+route,{waitUntil:'networkidle'}); await p.waitForTimeout(900);
   const ov=await p.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);
   console.log(`${name} ${tag}: h-overflow=${ov}`);
   if(name!=='wide') await p.screenshot({path:`shots/revamp/06_${name}_${tag}.png`,fullPage:false});
  }
  await ctx.close();
 }
 // --- landing untouched
 {
  const ctx=await b.newContext({viewport:{width:1440,height:900}});
  const p=await ctx.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(e.message));
  await p.goto(BASE+'/',{waitUntil:'networkidle'}); await p.waitForTimeout(2500);
  await p.screenshot({path:'shots/revamp/06_landing_after.png'});
  const hero=await p.$('.hero, [class*=hero]');
  console.log('landing: hero present =', !!hero, '| errors =', errs.length?errs[0]:'none');
  await ctx.close();
 }
 // --- inspector role gating
 {
  const ctx=await b.newContext({viewport:{width:1440,height:900},storageState:'inspector_state.json'});
  const p=await ctx.newPage();
  await p.goto(BASE+'/repository',{waitUntil:'networkidle'});
  const enf=await p.$('a[href="/dashboard"]');
  console.log('inspector: enforcement link hidden =', !enf);
  await p.goto(BASE+'/dashboard',{waitUntil:'networkidle'});
  const gate=await p.textContent('body');
  console.log('inspector: dashboard gated =', gate.includes('Admin access required'));
  await p.goto(BASE+'/scans/58',{waitUntil:'networkidle'});
  await p.waitForSelector('.finding',{timeout:10000});
  const vbtn=await p.$('button:has-text("Mark verified")');
  console.log('inspector: verify button hidden =', !vbtn);
  await ctx.close();
 }
 await b.close();
})();
