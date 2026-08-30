const { chromium } = require('playwright');
const BASE='http://127.0.0.1:5173';
(async()=>{
 const b=await chromium.launch();
 for(const theme of ['light','dark']){
  for(const [name,path,state] of [['login','/login',null],['repository','/repository','inspector_state.json'],['dashboard','/dashboard','admin_state.json']]){
   const ctx=await b.newContext({viewport:{width:1280,height:720},...(state?{storageState:state}:{})});
   await ctx.addInitScript(t=>{try{localStorage.setItem('lmpc-theme',t)}catch(e){}},theme);
   const p=await ctx.newPage();
   const errs=[]; p.on('pageerror',e=>errs.push(e.message));
   await p.goto(BASE+path,{waitUntil:'networkidle'}); await p.waitForTimeout(1400);
   await p.screenshot({path:`shots/14_${name}_${theme}.png`});
   const ov=await p.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
   console.log(`${theme}/${name}: overflow=${ov} errors=${errs.length?errs[0]:'none'}`);
   await ctx.close();
  }
 }
 await b.close();
})();
