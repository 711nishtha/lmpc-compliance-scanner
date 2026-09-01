const { chromium } = require('playwright');
(async()=>{
 const b=await chromium.launch();
 const ctx=await b.newContext({viewport:{width:1440,height:900}});
 const p=await ctx.newPage();
 await p.goto('http://localhost:5173/',{waitUntil:'networkidle'}); await p.waitForTimeout(2500);
 await p.screenshot({path:'shots/revamp/00_landing.png'});
 await b.close();
})();
