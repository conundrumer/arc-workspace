/* The detail head over the middle column: a live item's session tabs and
   turn buttons, or an unfinalized solver's rulings and reports. */
import { html } from "/vendor/htm-preact-standalone.module.js";
import { stageNames, backendOf, stageLabel, takeoverCmd, hasTab } from "/ui/item.js";
import { CompBadges, CalloutBadge, OwesBadge, StateChip } from "/ui/panels/badges.js";
import { post } from "/ui/server.js";
import { copy } from "/ui/toast.js";

export function DetailHead({it, cli, tab, badges, canAdvance, canResume, nxt, onTab, onDismiss}){
  const sid=it.sessions[tab];
  const context=(it.context||{})[tab];
  const resume = backendOf(it,tab)==="codex" ? "codex exec resume" : "claude --resume";
  return html`<div>
    <div class="dhead">
      <span class="tid">${it.id}</span>
      <${StateChip} state=${it.state}/>
      <span class="chip queued"><span class="dot"></span>${stageLabel(it,it.phase)}</span>
      ${it.updated && html`<span class="badge-upd">UPDATED</span>`}
      <${OwesBadge} x=${it}/>
      ${it.dirty && html`<span class="badge-dirty">CLEANUP PENDING</span>`}
      <${CompBadges} x=${it}/><${CalloutBadge} x=${it}/>
    </div>
    <div class="stabs">
      ${stageNames(it).filter(s=>hasTab(it,s)).map(s=>html`
        <span key=${s} class=${"stab"+(s===tab?" on":"")} onClick=${()=>onTab(s)}>
          ${stageLabel(it,s)}${badges[s] && html`<span class="bdg"></span>`}
        </span>`)}
    </div>
    ${/* The turn buttons lead, on a fixed-width command. The readouts and the
          two conveniences trail, since a growing context figure and a worker
          the console reaped mid-session both move whatever follows them. */
      (sid || it.active) && html`<div class="sessline">
      ${/* A turn the console has just sent has no session id yet: the id
            arrives with the turn's first event. The line is up from the
            send, so the stop button is there for the whole stretch. */
        sid
          ? html`<span class="cmd">${resume+" "+sid.slice(0,8)+"…"}</span>`
          : html`<span class="cmd">starting…</span>`}
      ${canResume && html`
        <button class="copybtn" title="continue the turn a usage limit cut off"
          onClick=${()=>post("/api/resume",{id:it.id})}>resume</button>`}
      ${canAdvance && html`
        <button class="copybtn" title="hand the report on"
          onClick=${()=>post("/api/advance",{id:it.id})}>${"advance · "+stageLabel(it,nxt)}</button>`}
      ${canAdvance && nxt==="finalize" && html`
        <button class="copybtn" title="record that no finalize pass is needed"
          onClick=${()=>onDismiss(it.id)}>✕ dismiss</button>`}
      ${it.active
        ? html`<button class="copybtn" onClick=${()=>post("/api/kill",{id:it.id})}>stop</button>`
        : html`<button class="copybtn" onClick=${()=>{
            if(confirm("Drop "+it.id+" from the console?")) post("/api/drop",{id:it.id});
          }}>drop</button>`}
      ${context && html`<span>${"context "+context.percent.toFixed(1)+"%"}</span>`}
      ${/* a codex stage reports no context window and compacts its own thread;
            `/compact` would reach it as prompt text, so the button stays off */
        context && backendOf(it,tab)!=="codex" && html`
        <button class="copybtn" disabled=${it.active}
          onClick=${()=>post("/api/compact",{id:it.id,sess:tab})}>
          ${"compact · "+(context.compactPct==null
            ? Math.round(context.used/1000)+"k rewrite"
            : "~"+context.compactPct.toFixed(2)+"% "+context.limiting)}</button>`}
      ${!(it.workerLive||{})[tab] && html`
        <button class="copybtn"
          onClick=${()=>copy(takeoverCmd(it,tab,cli),"takeover "+it.id)}>copy · o</button>`}
    </div>`}
  </div>`;
}

/* `ruling` is what the user already said of the solver, where they have:
   the rulings are made once, so a solver carrying one offers another pass
   instead of a second ruling. */
export function PeekHead({d, ruling, onDismiss, onApprove, onFinalize}){
  return html`<div class="dhead">
    <span class="tid">${d.id}</span>
    ${ruling
      ? html`<${StateChip} state=${ruling==="approved"?"approved":"committed"}
          label=${ruling}/>`
      : [html`<button key="a" class="copybtn" title="approve — record the ruling"
           onClick=${()=>onApprove(d.id)}>✓ approve</button>`,
         html`<button key="d" class="copybtn"
           title="dismiss — record that no finalize pass is needed"
           onClick=${()=>onDismiss(d.id)}>✕ dismiss</button>`]}
    <button class="copybtn" title="start a finalize pass over this solver"
      onClick=${()=>onFinalize(d.id)}>finalize</button>
  </div>`;
}
/* the solver's header lines and its review needs, above the reports */
function PeekNeeds({d}){
  const h=d.header||{}, needs=d.needs||{};
  const kinds=Object.keys(needs).filter(k=>(needs[k]||[]).length);
  if(!h.input && !h.output && !kinds.length) return null;
  return html`<div class="peekneeds">
    ${h.input && html`<div><span class="lbl">input</span> ${h.input}</div>`}
    ${h.output && html`<div><span class="lbl">output</span> ${h.output}</div>`}
    ${kinds.map(k=>html`<div key=${k}><span class="lbl">${k}</span>
      <ul>${needs[k].map((t,i)=>html`<li key=${i}>${t}</li>`)}</ul></div>`)}
  </div>`;
}
export function PeekBody({d}){
  const reports=d.reports||[];
  return html`<div id="judge-scroll">
    <${PeekNeeds} d=${d}/>
    ${reports.map((r,i)=>[
      html`<div class="railhead" key=${"h"+i}><span>${r.stage+" report"}</span></div>`,
      html`<pre class="peektext" key=${"t"+i}>${r.text}</pre>`,
      r.diff && html`<div class="railhead" key=${"dh"+i}><span>${r.stage+" diff"}</span></div>`,
      r.diff && html`<pre class="peektext" key=${"d"+i}>${r.diff}</pre>`,
    ])}
    ${!reports.length && html`<p class="placeholder">no reports</p>`}
  </div>`;
}
