const { chromium } = require('playwright');
const BASE='http://localhost:5173';
async function mk(email,pass,role,file){
 const b=await chromium.launch(); const ctx=await b.newContext({viewport:{width:1440,height:900}});
 const p=await ctx.newPage();
 await p.goto(BASE+'/login',{waitUntil:'networkidle'});
 // register (may already exist -> falls back to login)
 const resp = await p.evaluate(async ([e,pw,r])=>{
   let res = await fetch('/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,password:pw,role:r})});
   if(!res.ok) res = await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,password:pw})});
   const d = await res.json();
   localStorage.setItem('lmpc_token', d.access_token); localStorage.setItem('lmpc_role', d.role);
   return d.role;
 },[email,pass,role]);
 await ctx.storageState({path:file});
 console.log(file,'->',resp);
 await b.close();
}
(async()=>{
 await mk('admin1@example.com','password123','admin','admin_state.json');
 await mk('inspector1@example.com','password123','inspector','inspector_state.json');
})();
