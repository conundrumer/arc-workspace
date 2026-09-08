/* The overnight panel. */
import { html, useEffect, useRef } from "/vendor/htm-preact-standalone.module.js";
import { hhmm, hhmmDay } from "/ui/prose.js";

/* ---------- overnight ----------
   The dials are the server's; the panel only mirrors them, so an edit posts
   and the next poll confirms it. A field the user is typing in is left alone.
   The source picks what an admission is: a queue task, the finalize pass of
   the next unfinalized solver, or both side by side. Each slot has its own
   target, and the panel shows the dials of the slots the source admits into.
   The pace picks whether the week's quota is shared with work outside the
   console or spent to the wall; the pace-line dials show only under share,
   and the balance box only where the two windows race, under exhaust with
   both slots. */
export const NIGHT_SOURCES = ["queue","unfinalized","both"];
export const PACE_MODES = ["share","exhaust"];
const TARGET_KEYS = {queue:["target"], unfinalized:["finalize_target"], both:["target","finalize_target"]};
export const targetKeys = n => TARGET_KEYS[n.source] || TARGET_KEYS.queue;
const LINE_DIALS = ["reserve","floor"];
const lineDials = n => n.pace==="exhaust" ? [] : LINE_DIALS;
/* a window's 100% time: a clock time, "?" with no rate yet, else the
   server's word for it */
const eta = v => v==null ? "?" : typeof v==="number" ? hhmmDay(v) : String(v);
const ETA_HELP = "when each window hits 100%: at the current rate; once an hour of one more item is set aside; and the time the gate holds against";


export function NightPanel({night, open, onDial, onToggle, onCatchup, onBalance, onSource, onPace}){
  const n = night||{}, g = n.gate, tkeys = targetKeys(n), share = n.pace!=="exhaust";
  const races = !share && n.source==="both";
  const refs = {target:useRef(null), finalize_target:useRef(null),
                reserve:useRef(null), floor:useRef(null)};
  const log = useRef(null), onBox = useRef(null), catchBox = useRef(null),
        balBox = useRef(null);
  useEffect(()=>{
    for(const key of [...tkeys, ...lineDials(n)]){
      const el=refs[key].current, v=n[key];
      if(el && v!=null && document.activeElement!==el && el.value!==String(v)) el.value=v;
    }
    /* the boxes mirror the server, so a click the server does not confirm —
       a declined autopilot prompt — snaps back on the next draw */
    if(onBox.current) onBox.current.checked=!!n.on;
    if(catchBox.current) catchBox.current.checked=!!n.catchup;
    if(balBox.current) balBox.current.checked=!!n.balance;
    if(log.current) log.current.scrollTop=log.current.scrollHeight;
  });
  const read=[];
  /* each window the admission draws: when it reaches 100% at the rate the
     fleet is showing, when it runs out once an hour of one more item is set
     aside, and the time the gate holds against. A red +1 is the spend hold. */
  const wins=(g && g.windows) || [];
  if(wins.length) read.push(html`<table key="win">
    <tr title=${ETA_HELP}><th></th><th>now</th><th>+1</th><th>limit</th></tr>
    ${wins.map(w=>html`<tr key=${w.label}
        title=${"rate "+w.rate.toFixed(1)+" · share "+w.share.toFixed(1)+" · pace "+w.budget.toFixed(1)+" points/h"}>
      <td><b>${w.label}</b></td><td>${eta(w.runs_out)}</td>
      <td class=${typeof w.runs_out_more==="number" && w.runs_out_more < w.limit ? "gate-held" : null}>
        ${eta(w.runs_out_more)}</td><td>${eta(w.limit)}</td></tr>`)}
  </table>`);
  if(g && g.wk!=null && g.line!=null)
    read.push(html`<div key="wk" title=${"the line is elapsed "+g.elapsed.toFixed(1)+"% less the reserve of "+n.reserve}>
      wk <b>${g.wk.toFixed(0)+"%"}</b> vs line <b>${g.line.toFixed(0)+"%"}</b></div>`);
  if(g) read.push(html`<div key="gate" class=${g.open?"gate-open":"gate-held"}>
    ${g.verdict}</div>`);
  else read.push(html`<div key="off">admissions are yours</div>`);
  if(n.next) read.push(html`<div key="next">${"next "+n.next.what+" "+hhmm(n.next.at)}</div>`);
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
      <label hidden=${!races} title="keep the weekly and Fable windows within a few points of each other; whichever leads holds its slot">
        <input ref=${balBox} type="checkbox" checked=${!!n.balance}
          onChange=${e=>onBalance(e.target.checked)}/>
        balance</label>
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
    <div class="nightbody">
      <div class="nightread">${read}</div>
      <div id="nightlog" ref=${log}>
        ${(n.log||[]).map((e,i)=>html`<div key=${i+":"+e.t}>${hhmm(e.t)+" · "+e.text}</div>`)}
      </div>
    </div>
  </div>`;
}
