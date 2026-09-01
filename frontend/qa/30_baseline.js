const { chromium } = require('playwright');
const BASE='http://localhost:5173';
(async()=>{
 const b=await chromium.launch();
 const pages=[['login','/login',null],['dashboard','/dashboard','admin_state.json'],
              ['repository','/repository','admin_state.json'],['scan','/scan','admin_state.json'],
              ['detail','/scans/58','admin_state.json']];
 for(const [name,path,state] of pages){
  try{
   const ctx=await b.newContext({viewport:{width:1440,height:900},...(state?{storageState:state}:{})});
   const p=await ctx.newPage();
   await p.goto(BASE+path,{waitUntil:'networkidle'}); await p.waitForTimeout(1500);
   await p.screenshot({path:`shots/revamp/00_before_${name}.png`,fullPage:true});
   console.log(name,'ok');
   await ctx.close();
  }catch(e){console.log(name,'ERR',e.message.split('\n')[0])}
 }
 await b.close();
})();
