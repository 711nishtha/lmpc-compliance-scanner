const { chromium } = require('playwright');
const BASE='http://127.0.0.1:5173';
(async()=>{
 const b=await chromium.launch({args:['--use-gl=angle','--enable-gpu']});
 for(const [name,vp] of [['desktop',{width:1280,height:720}],['mobile',{width:390,height:844}]]){
  const ctx=await b.newContext({viewport:vp, ...(name==='mobile'?{hasTouch:true,isMobile:true}:{})});
  await ctx.addInitScript(()=>{try{localStorage.setItem('lmpc-theme','dark')}catch(e){}});
  const p=await ctx.newPage();
  await p.goto(BASE,{waitUntil:'networkidle'});
  await p.waitForTimeout(3000);
  await p.screenshot({path:`shots/15_hero_${name}.png`});
  // full page to see how far the dark treatment extends
  await p.screenshot({path:`shots/15_full_${name}.png`, fullPage:true});
  console.log(`${name} captured`);
  await ctx.close();
 }
 await b.close();
})();
