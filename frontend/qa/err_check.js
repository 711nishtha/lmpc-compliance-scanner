const { chromium } = require('playwright');
(async()=>{
 const b=await chromium.launch();
 const p=await b.newPage();
 p.on('console',m=>console.log('CONSOLE',m.type(),m.text().slice(0,200)));
 p.on('pageerror',e=>console.log('PAGEERROR:',e.message));
 await p.goto('http://127.0.0.1:5173',{waitUntil:'networkidle'});
 await p.waitForTimeout(2500);
 console.log('BODY TEXT LEN:', (await p.evaluate(()=>document.body.innerText)).length);
 console.log('ROOT HTML:', (await p.evaluate(()=>document.getElementById('root').innerHTML)).slice(0,300));
 await b.close();
})();
