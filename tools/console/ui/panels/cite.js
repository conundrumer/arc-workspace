/* Grid citations: a chip in the prose shows its grid in a popup on hover,
   pins on click, and closes on escape or a click away. */
import { html, useState, useEffect, useMemo } from "/vendor/htm-preact-standalone.module.js";
import { Grid, parsePlaces } from "/ui/panels/grid.js";
import { ensureTask } from "/ui/server.js";

export function CitePop({cite, task, onClose}){
  const m=/^(train|test)(\d)$/.exec(cite.pair);
  const grid=(task && typeof task!=="string" && (task[m[1]]||[])[+m[2]] || {})[cite.side];
  const places=useMemo(()=>parsePlaces(cite.places),[cite.places]);
  const oob=grid ? places.filter(p=>(p.r0??0)>grid.length-1 || (p.c0??0)>grid[0].length-1) : [];
  const style={left:Math.max(8, Math.min(cite.x, window.innerWidth-360))+"px",
               top:Math.max(8, Math.min(cite.y+6, window.innerHeight-320))+"px"};
  return html`<div id="citepop" style=${style}>
    <div class="cphead">${cite.tid} · ${cite.pair} ${cite.side}
      ${cite.pinned && html`<button class="cpx" onClick=${onClose}>×</button>`}</div>
    ${!task || task==="pending" ? html`<div class="cpnote">loading…</div>`
      : task==="missing" ? html`<div class="cpnote">no task data</div>`
      : !grid ? html`<div class="cpnote">no ${cite.pair} ${cite.side} in this task</div>`
      : html`<${Grid} g=${grid} places=${places}/>`}
    ${oob.length>0 && html`<div class="cpnote">cited place outside the ${grid.length}×${grid[0].length} grid</div>`}
  </div>`;
}


/* Chips are static spans out of md(), so one delegated set of listeners
   serves every feed render; the task id rides on the feed container. */
export function useCitations(){
  const [cite,setCite]=useState(null);  // hovered/pinned grid citation
  useEffect(()=>{
    const at=e=>{
      const chip=e.target.closest(".cite"), scope=chip && chip.closest("[data-tid]");
      if(!scope) return null;
      const r=chip.getBoundingClientRect();
      return {tid:scope.dataset.tid, pair:chip.dataset.pair, side:chip.dataset.side,
              places:chip.dataset.places, x:r.left, y:r.bottom};
    };
    const over=e=>{
      const c=at(e);
      if(c){ ensureTask(c.tid); setCite(p=>p && p.pinned ? p : c); }
      else if(!e.target.closest("#citepop")) setCite(p=>p && !p.pinned ? null : p);
    };
    const click=e=>{
      const c=at(e);
      if(c){ ensureTask(c.tid); setCite({...c, pinned:true}); }
      else if(!e.target.closest("#citepop")) setCite(null);
    };
    const key=e=>{ if(e.key==="Escape") setCite(null); };
    document.addEventListener("mouseover",over);
    document.addEventListener("click",click);
    document.addEventListener("keydown",key);
    return ()=>{
      document.removeEventListener("mouseover",over);
      document.removeEventListener("click",click);
      document.removeEventListener("keydown",key);
    };
  },[]);
  return [cite, ()=>setCite(null)];
}
