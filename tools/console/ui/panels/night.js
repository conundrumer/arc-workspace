/* The overnight panel. */
import { html, useEffect, useRef } from "/vendor/htm-preact-standalone.module.js";
import { hhmm } from "/ui/prose.js";

/* ---------- overnight ----------
   The dials are the server's; the panel only mirrors them, so an edit posts
   and the next poll confirms it. A field the user is typing in is left alone.
   The source picks what an admission is: a queue task, the finalize pass of
   the next unfinalized solver, or both side by side. Each slot has its own
   target, and the panel shows the dials of the slots the source admits into.
   The pace picks whether the week's quota is shared with work outside the
   console or spent to the wall; the pace-line dials show only under share. */
export const NIGHT_SOURCES = ["queue","unfinalized","both"];
export const PACE_MODES = ["share","exhaust"];
const TARGET_KEYS = {queue:["target"], unfinalized:["finalize_target"], both:["target","finalize_target"]};
export const targetKeys = n => TARGET_KEYS[n.source] || TARGET_KEYS.queue;
const LINE_DIALS = ["reserve","floor"];
const lineDials = n => n.pace==="exhaust" ? [] : LINE_DIALS;


export function NightPanel({night, open, onDial, onToggle, onCatchup, onSource, onPace}){
  const n = night||{}, g = n.gate, tkeys = targetKeys(n), share = n.pace!=="exhaust";
  const refs = {target:useRef(null), finalize_target:useRef(null),
                reserve:useRef(null), floor:useRef(null)};
  const log = useRef(null), onBox = useRef(null), catchBox = useRef(null);
  useEffect(()=>{
    for(const key of [...tkeys, ...lineDials(n)]){
      const el=refs[key].current, v=n[key];
      if(el && v!=null && document.activeElement!==el && el.value!==String(v)) el.value=v;
    }
    /* the boxes mirror the server, so a click the server does not confirm —
       a declined autopilot prompt — snaps back on the next draw */
    if(onBox.current) onBox.current.checked=!!n.on;
    if(catchBox.current) catchBox.current.checked=!!n.catchup;
    if(log.current) log.current.scrollTop=log.current.scrollHeight;
  });
  const read=[];
  if(g && g.wk!=null && g.line!=null)
    read.push(html`<span key="wk">wk <b>${g.wk.toFixed(1)+"%"}</b> vs line <b>${g.line.toFixed(1)+"%"}</b>
      ${" (elapsed "+g.elapsed.toFixed(1)+"% − reserve "+n.reserve+")"}</span>`);
  /* each window the admission draws: the fleet's rate plus one more item's
     share, against what the window can take an hour */
  for(const w of (g && g.windows) || [])
    read.push(html`<span key=${w.label} title="fleet rate + one item's share vs the window's budget, points an hour">
      ${w.label} <b>${w.pct.toFixed(0)+"%"}</b>${" · "+w.rate.toFixed(1)+"+"+w.share.toFixed(1)+" vs "+w.budget.toFixed(1)+"/h"}</span>`);
  if(g) read.push(html`<span key="gate" class=${g.open?"gate-open":"gate-held"}>
    ${(g.open?"admission open · ":"admission held · ")+g.why}</span>`);
  else read.push(html`<span key="off">admissions are yours</span>`);
  if(n.next) read.push(html`<span key="next">${"next: "+n.next.what+" "+hhmm(n.next.at)}</span>`);
  return html`<div id="nightpanel" hidden=${!open}>
    <div class="nightrow">
      <label title="run the queue unattended">
        <input ref=${onBox} type="checkbox" checked=${!!n.on}
          onChange=${e=>onToggle(e.target.checked)}/>
        <b>autopilot</b></label>
      <label title="what an admission is: a queue task run up to finalize, the finalize pass of the next unfinalized solver, or one of each">source
        <select value=${n.source||"queue"} onChange=${e=>onSource(e.target.value)}>
          ${NIGHT_SOURCES.map(src=>html`<option key=${src} value=${src}>${src}</option>`)}
        </select></label>
      <label title="share: hold weekly quota back along a pace line; exhaust: spend the week to its limits, keeping only the headroom the turns in flight need">pace
        <select value=${n.pace||"share"} onChange=${e=>onPace(e.target.value)}>
          ${PACE_MODES.map(m=>html`<option key=${m} value=${m}>${m}</option>`)}
        </select></label>
      ${tkeys.map(key=>html`<label key=${key} title=${key==="finalize_target"
            ? "finalize passes kept in flight" : "items kept in flight"}>
        ${tkeys.length>1 && key==="finalize_target" ? "finalize target" : "target"}
        <input ref=${refs[key]} type="number" min="1" max="40"
          onChange=${e=>onDial(key, e.target.value)}/></label>`)}
      <label hidden=${!share} title="weekly points held back from the pace line">reserve
        <input ref=${refs.reserve} type="number" min="0" max="100"
          onChange=${e=>onDial("reserve", e.target.value)}/></label>
      <label hidden=${!share} title="weekly points free to spend early in the week">floor
        <input ref=${refs.floor} type="number" min="0" max="100"
          onChange=${e=>onDial("floor", e.target.value)}/></label>
      <label hidden=${!share} title="spend the week's slack">
        <input ref=${catchBox} type="checkbox" checked=${!!n.catchup}
          onChange=${e=>onCatchup(e.target.checked)}/>
        catchup</label>
      <span style="flex:1"></span>
      <span><b>${n.landed||0}</b> landed unreviewed tonight</span>
    </div>
    <div class="nightrow">${read}</div>
    <div id="nightlog" ref=${log}>
      ${(n.log||[]).map((e,i)=>html`<div key=${i+":"+e.t}>${hhmm(e.t)+" · "+e.text}</div>`)}
    </div>
  </div>`;
}
