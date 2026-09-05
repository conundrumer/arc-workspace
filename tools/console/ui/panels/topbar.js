/* The top bar, two rows. The readouts row: the lens switch, the wave
   counts, the usage windows. The controls row: the autopilot and committer
   panels, the automatic-move toggles, the next wave, the commit. */
import { html } from "/vendor/htm-preact-standalone.module.js";
import { useClock } from "/ui/clock.js";
import { FINAL, STATES } from "/ui/item.js";
import { StateChip } from "/ui/panels/badges.js";
import { pad2 } from "/ui/prose.js";

/* account rate-limit windows, statusline style: 5h➞1pm 40%/62% */
function resetLabel(epoch, weekly){
  const d=new Date(Math.round(epoch/1800)*1800*1000);
  const h=d.getHours(), m=d.getMinutes(), ap=h>=12?"pm":"am", h12=h%12||12;
  const t=m ? h12+":"+String(m).padStart(2,"0")+ap : h12+ap;
  return weekly ? ["sun","mon","tue","wed","thu","fri","sat"][d.getDay()]+","+t : t;
}
export function Usage({usage}){
  useClock();   // the pace target moves with the time left in a window
  return html`<span id="usage">${usage.map((w,i)=>{
    const cls = w.pct>=70?"uhot":w.pct>=45?"uwarn":"uok";
    let txt = w.label;
    if(w.reset) txt += "➞"+resetLabel(w.reset, w.window>6*86400);
    txt += " "+Math.floor(w.pct)+"%";
    if(w.reset){
      const target=Math.max(0,Math.min(100,Math.round(100*(1-(w.reset-Date.now()/1000)/w.window))));
      txt += "/"+target+"%";
    }
    return html`<span key=${w.label+i} class=${cls}>${txt}</span>`;
  })}</span>`;
}

export function Topbar({view, setView, wave, items, progress, usage, night, nightOpen, toggleNight,
                 committer, commitOpen, toggleCommit, onCommit, waveCtl,
                 auto, onAuto, extra}){
  const tally={};
  items.forEach(it=>tally[it.state]=(tally[it.state]||0)+1);
  const gate = (night||{}).gate;
  const nightCls = night && night.on ? (gate&&gate.open?"on":"held") : "";
  const nightTxt = night && night.on
    ? "autopilot "+(night.slots||[]).map(s=>s.live+"/"+s.target).join(" · ")
      +" · "+(gate&&gate.open?"open":"held")
    : "autopilot";
  return html`<div id="topbar">
    <div class="row readouts">
      <span class="wordmark"><b>arc</b> · solver console</span>
      <span class="viewtog">
        <button class=${view!==FINAL?"on":""} onClick=${()=>setView("wave")}>wave</button>
        <button class=${view===FINAL?"on":""} onClick=${()=>setView(FINAL)}>finalize</button>
      </span>
      <span class="chip queued mono">${"wave "+pad2(wave)}</span>
      <span class="chip queued mono" hidden=${!progress}>
        ${progress ? progress.solved+"/"+progress.total+" solvers" : ""}
      </span>
      <span id="counts">${STATES.filter(st=>tally[st]).map(st=>html`
        <${StateChip} key=${st} state=${st} label=${tally[st]+" "+(st==="needs-review"?"to review":st)}/>`)}
      </span>
      <${Usage} usage=${usage}/>
    </div>
    <div class="row controls">
      <button id="nightbtn" class=${nightCls} onClick=${toggleNight}>${nightTxt}</button>
      <span class="wavectl">
        <label title="a landing whose next stage is finalize hands on by itself">
          <input type="checkbox" checked=${!!auto.finalize}
            onChange=${e=>onAuto("finalize", e.target.checked)}/>auto finalize</label>
        <label title="compact an unapproved finalize session before its cache goes cold or its worker is reaped">
          <input type="checkbox" checked=${!!auto.compact}
            onChange=${e=>onAuto("compact", e.target.checked)}/>auto compact</label>
        <label title="compact a finalize session the autopilot opened as soon as its callouts land">
          <input type="checkbox" checked=${!!auto.compact_landing}
            onChange=${e=>onAuto("compact_landing", e.target.checked)}/>compact on landing</label>
      </span>
      <button id="commitbtn" class=${committer.running?"on":""}
        hidden=${!committer.running && !(committer.feed||[]).length}
        title="what the committer session says and runs" onClick=${toggleCommit}>
        ${committer.running?"committing…":"committer"}</button>
      <span class="wavectl push" title="start the next wave">wave
        <input type="number" min="1" max="20" aria-label="wave size"
          value=${waveCtl.k} onInput=${e=>waveCtl.setK(e.target.value)}/>
        <select aria-label="wave order" value=${waveCtl.order} onChange=${e=>waveCtl.setOrder(e.target.value)}>
          <option value="name">name order</option>
          <option value="size">simplest</option>
        </select>
        <button disabled=${waveCtl.busy} onClick=${waveCtl.start}>start</button>
      </span>
      ${extra}
      <button class="primary" disabled=${!items.some(it=>it.state==="approved")}
        onClick=${onCommit}>commit approved</button>
    </div>
  </div>`;
}
