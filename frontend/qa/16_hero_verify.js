const { chromium } = require('playwright');
const BASE='http://127.0.0.1:5173';
(async()=>{
 const b=await chromium.launch({args:['--use-gl=angle','--enable-gpu']});
 for(const [name,vp,mob] of [['desktop',{width:1280,height:720},false],['mobile',{width:390,height:844},true]]){
  const ctx=await b.newContext({viewport:vp,...(mob?{hasTouch:true,isMobile:true}:{})});
  const p=await ctx.newPage();
  const errs=[]; p.on('pageerror',e=>errs.push(e.message));
  await p.goto(BASE,{waitUntil:'networkidle'});
  await p.waitForTimeout(2000);
  const t1=await p.evaluate(()=>document.querySelector('.hero-video')?.currentTime);
  await p.waitForTimeout(1800);
  const r=await p.evaluate(()=>{
    const vw=window.innerWidth, vh=window.innerHeight;
    const v=document.querySelector('.hero-video');
    const stage=document.querySelector('.hero-stage').getBoundingClientRect();
    const nav=document.querySelector('.hero-nav').getBoundingClientRect();
    const content=document.querySelector('.hero-content').getBoundingClientRect();
    // anything sticking out past the viewport horizontally?
    const clipped=[...document.querySelectorAll('.hero-stage *, .hero-nav *')]
      .map(e=>({c:e.className&&e.className.baseVal===undefined?e.className:'', r:e.getBoundingClientRect()}))
      .filter(o=>typeof o.c==='string'&&o.c&&(o.r.right>vw+1||o.r.left<-1)&&o.r.width>0)
      .map(o=>`${o.c.split(' ')[0]}[${Math.round(o.r.left)},${Math.round(o.r.right)}]`);
    return {
      vw, vh,
      stageH: Math.round(stage.height), fillsViewport: stage.height>=vh-2,
      videoPlaying: v && !v.paused, videoReady: v?v.readyState:null,
      videoCovers: v ? (v.getBoundingClientRect().width>=vw-2) : false,
      navOverlapsContent: nav.bottom > content.top,
      contentCentered: Math.abs((content.left+content.right)/2 - vw/2) < 2,
      clipped,
      overflowX: document.documentElement.scrollWidth > vw,
      floaters: document.querySelectorAll('.floater, .floaters, .scene-chip').length,
    };
  });
  const fps=await p.evaluate(()=>new Promise(res=>{let f=0;const t0=performance.now();
    (function l(){f++;performance.now()-t0<3000?requestAnimationFrame(l):res(+(f/((performance.now()-t0)/1000)).toFixed(1));})();}));
  const t2=await p.evaluate(()=>document.querySelector('.hero-video')?.currentTime);
  console.log(`\n--- ${name} ---`);
  console.log(JSON.stringify(r,null,1));
  console.log(`video advanced: ${t1?.toFixed(2)} -> ${t2?.toFixed(2)} (${t2>t1?'PLAYING':'FROZEN'})`);
  console.log(`FPS: ${fps}`);
  console.log(`errors: ${errs.length?errs[0]:'none'}`);
  await ctx.close();
 }
 await b.close();
})();
