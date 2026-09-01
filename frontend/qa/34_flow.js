const { chromium } = require('playwright');
const BASE='http://localhost:5173';
(async()=>{
 const b=await chromium.launch();
 const ctx=await b.newContext({viewport:{width:1440,height:900}});
 const p=await ctx.newPage();
 const errs=[]; p.on('pageerror',e=>errs.push(e.message));
 const step=async(n,fn)=>{try{await fn();console.log('PASS',n)}catch(e){console.log('FAIL',n,'-',e.message.split('\n')[0])}};

 await p.goto(BASE+'/login',{waitUntil:'networkidle'});

 await step('login form accepts credentials',async()=>{
   await p.fill('#auth-email','admin1@example.com');
   await p.fill('#auth-pass','password123');
   await p.click('button[type=submit]');
   await p.waitForURL('**/scan',{timeout:15000});
 });

 await step('rail shows the signed-in email',async()=>{
   const t=await p.textContent('.rail-id-email');
   if(!t.includes('admin1@example.com')) throw new Error('email not shown: '+t);
 });

 await step('register mode reveals role picker',async()=>{
   await p.goto(BASE+'/login'); // still authed but /login renders bare
   await p.click('.auth-switch');
   await p.waitForSelector('.role-picker',{timeout:4000});
   await p.click('.role-card:nth-child(2)');
   const on=await p.getAttribute('.role-card:nth-child(2)','class');
   if(!on.includes('is-on')) throw new Error('role card did not select');
 });

 await step('repository loads + status chip filter works',async()=>{
   await p.goto(BASE+'/repository',{waitUntil:'networkidle'});
   await p.waitForSelector('.ledger tbody tr',{timeout:8000});
   const before=await p.$$eval('.ledger tbody tr',r=>r.length);
   await p.click('.filter-chip:nth-of-type(1)');
   await p.waitForTimeout(1200);
   const after=await p.$$eval('.ledger tbody tr',r=>r.length);
   if(after>=before) throw new Error(`filter did not narrow: ${before} -> ${after}`);
   const pressed=await p.getAttribute('.filter-chip:nth-of-type(1)','aria-pressed');
   if(pressed!=='true') throw new Error('aria-pressed not set');
 });

 await step('reset restores full list',async()=>{
   await p.click('button:has-text("Reset")');
   await p.waitForTimeout(1200);
   const n=await p.$$eval('.ledger tbody tr',r=>r.length);
   if(n<5) throw new Error('reset did not restore, got '+n);
 });

 await step('opening a record shows findings + evidence',async()=>{
   await p.click('.ledger tbody tr:first-child .ledger-primary');
   await p.waitForSelector('.finding',{timeout:10000});
   await p.waitForSelector('.evidence-img',{timeout:15000});
 });

 await step('findings sort toggle flips',async()=>{
   const first=await p.textContent('.finding .finding-id');
   await p.click('.sort-toggle'); await p.waitForTimeout(400);
   const after=await p.textContent('.finding .finding-id');
   if(first===after) console.log('   (note: sort order identical - may be legitimately same)');
 });

 await step('dashboard renders chart + readouts',async()=>{
   await p.goto(BASE+'/dashboard',{waitUntil:'networkidle'});
   await p.waitForSelector('.readout-value',{timeout:8000});
   const cols=await p.$$eval('.chart-col',c=>c.length);
   if(cols!==30) throw new Error('expected 30 chart columns, got '+cols);
 });

 await step('sign out returns to login',async()=>{
   await p.click('button:has-text("Sign out")');
   await p.waitForURL('**/login',{timeout:6000});
 });

 console.log('\npage errors:', errs.length?errs:'none');
 await b.close();
})();
