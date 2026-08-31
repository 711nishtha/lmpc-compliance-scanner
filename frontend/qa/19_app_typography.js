const { chromium } = require('playwright');
const BASE='http://127.0.0.1:5173';
(async()=>{
 const b=await chromium.launch();
 for(const theme of ['light','dark']){
  const ctx=await b.newContext({viewport:{width:1280,height:720},storageState:'inspector_state.json'});
  await ctx.addInitScript(t=>{try{localStorage.setItem('lmpc-theme',t)}catch(e){}},theme);
  const p=await ctx.newPage();
  await p.goto(BASE+'/scans/1',{waitUntil:'networkidle'});
  await p.waitForTimeout(1500);
  await p.screenshot({path:`shots/19_scandetail_${theme}.png`});
  await ctx.close();
 }
 await b.close();
 console.log('done');
})();
