/* ARC grids: the palette, a grid drawn cell by cell with cited places
   marked, the places a citation names, and a task's thumbnail. */
import { html, useEffect, useRef } from "/vendor/htm-preact-standalone.module.js";

export const ARC = ["#000000","#0074D9","#FF4136","#2ECC40","#FFDC00","#AAAAAA","#F012BE","#FF851B","#7FDBFF","#870C25"];

function cellPx(w,h){ const m=Math.max(w,h); return m<=10?16:m<=15?12:m<=22?9:7; }
/* label: one name, or the several names of a grid that stands for more than
   one case, a line each. The size follows the first line. */
export function Grid({g, label, places}){
  const w=g[0].length, h=g.length, px=cellPx(w,h);
  const lines = !label ? [] : (Array.isArray(label) ? label : [label]);
  return html`<div class="gwrap">
    ${lines.map((s,i)=>html`<div class="glabel" key=${s}>
      ${i===0 ? s+" · "+h+"×"+w : s}</div>`)}
    <div class="agrid" style=${{"--cell":px+"px", gridTemplateColumns:`repeat(${w},${px}px)`}}>
      ${g.map((row,y)=>row.map((v,x)=>html`<div key=${y+":"+x}
        class=${places && covers(places,y,x) ? "hl" : null}
        style=${{background:ARC[v]}}></div>`))}
    </div>
  </div>`;
}

/* A place from a chip's citation text: a point carries both axes; a rows or
   cols spec carries one, and a cols spec directly after a rows-only place
   intersects with it (the corpus's box form) instead of starting a band. */
export function parsePlaces(s){
  const out=[];
  for(const m of s.matchAll(/\(\s*(\d+)\s*,\s*(\d+)\s*\)|(rows?|cols?|columns?) ?(\d+)(?: ?[–-] ?(\d+))?/g)){
    if(m[1]!==undefined){ out.push({r0:+m[1], r1:+m[1], c0:+m[2], c1:+m[2]}); continue; }
    const a=+m[4], b=m[5]===undefined ? a : +m[5], prev=out[out.length-1];
    if(m[3][0]==="r") out.push({r0:a, r1:b});
    else if(prev && prev.c0===undefined){ prev.c0=a; prev.c1=b; }
    else out.push({c0:a, c1:b});
  }
  return out;
}
export const covers=(ps,r,c)=>ps.some(p=>
  (p.r0===undefined || (r>=p.r0 && r<=p.r1)) &&
  (p.c0===undefined || (c>=p.c0 && c<=p.c1)));

export function Thumb({task}){
  const ref=useRef(null);
  const ok = !!task && typeof task!=="string";
  useEffect(()=>{
    const cv=ref.current;
    if(!cv || !ok) return;
    const g=task.train[0].input;
    const w=g[0].length, h=g.length, px=Math.max(1,Math.floor(30/Math.max(w,h)));
    cv.width=w*px; cv.height=h*px;
    const ctx=cv.getContext("2d");
    g.forEach((row,y)=>row.forEach((v,x)=>{ ctx.fillStyle=ARC[v]; ctx.fillRect(x*px,y*px,px,px); }));
  },[task, ok]);
  return ok ? html`<canvas ref=${ref}></canvas>` : html`<div class="thumb-ph"></div>`;
}
