const { chromium } = require('playwright');
const BASE='http://localhost:5173';
const tag = process.argv[2] || 'x';
const only = process.argv[3];
const PAGES=[['login','/login',null],['dashboard','/dashboard','admin_state.json'],
             ['repository','/repository','admin_state.json'],['scan','/scan','admin_state.json'],
             ['detail','/scans/58','admin_state.json']];
(async()=>{
 const b=await chromium.launch();
 for(const [name,path,state] of PAGES){
  if(only && only!==name) continue;
  for(const theme of ['dark','light']){
   try{
    const ctx=await b.newContext({viewport:{width:1440,height:900},...(state?{storageState:state}:{})});
    await ctx.addInitScript(t=>{try{localStorage.setItem('lmpc-theme',t)}catch(e){}},theme);
    const p=await ctx.newPage();
    const errs=[]; p.on('pageerror',e=>errs.push(e.message));
    await p.goto(BASE+path,{waitUntil:'networkidle'}); await p.waitForTimeout(1600);
    await p.screenshot({path:`shots/revamp/${tag}_${name}_${theme}.png`,fullPage:true});
    const ov=await p.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);
    console.log(`${name}/${theme}: overflow=${ov} err=${errs[0]||'none'}`);
    await ctx.close();
   }catch(e){console.log(name,theme,'ERR',e.message.split('\n')[0])}
  }
 }
 await b.close();
})();
