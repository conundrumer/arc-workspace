/* The small marks a row and a detail head share: state chips, comp and
   entry badges, the callout count. */
import { html } from "/vendor/htm-preact-standalone.module.js";

export const CHIPCLS = {"needs-review":"review","commented":"commented","running":"running","queued":"queued","approved":"approved","committed":"committed"};

export function CompBadges({x}){
  const comps=x.comps||[];
  return comps.map(c=>{
    const bad=(x.comps_unproposed||[]).includes(c);
    return html`<span key=${c} class=${"badge-comp"+(bad?" unproposed":"")}
      title=${bad?"no proposals entry":"proposals entry open"}>${c}</span>`;
  }).concat((x.entries||[]).filter(e=>!comps.includes(e)).map(e=>
    html`<span key=${"e:"+e} class="badge-comp entry"
      title="proposals entry this task added, with no comp">${e}</span>`));
}
/* the review needs a solver holds, one badge per kind with its count; the
   kind the priority names leads, and the proposal kind is the comp badges */
export const NEED_KINDS = ["principle","proposal","workaround","sweep"];
/* A need line runs to a sentence or more, and a solver holds many of them,
   so the tooltip takes a few lines cut to a readable width; the peek pane
   carries them in full. */
const TIP_LINES = 6, TIP_WIDTH = 96;
function tip(lines){
  const shown=lines.slice(0, TIP_LINES).map(t=>
    t.length>TIP_WIDTH ? t.slice(0, TIP_WIDTH-1)+"…" : t);
  const rest=lines.length-shown.length;
  return (rest>0 ? shown.concat("…and "+rest+" more") : shown).join("\n");
}
export function NeedBadges({x, priority}){
  const needs=x.needs||{};
  const kinds=[priority, ...NEED_KINDS.filter(k=>k!==priority)].filter(k=>NEED_KINDS.includes(k));
  return kinds.map(k=>{
    if(k==="proposal") return html`<${CompBadges} key="proposal" x=${x}/>`;
    const lines=needs[k]||[];
    if(!lines.length) return null;
    return html`<span key=${k} class=${"badge-need "+k+(k===priority?" lead":"")}
      title=${tip(lines)}>${k} ${lines.length}</span>`;
  });
}
/* what the stage left for the user; the entries ride along in the tooltip */
export function CalloutBadge({x}){
  if(!x.callout_n) return null;
  const r = x.callout_rank;
  return html`<span class=${"badge-call"+(r!=null?" r"+r:"")} title=${(x.callouts||[]).join("\n")}>${r===0?"P0 · ":""}${x.callout_n}</span>`;
}
/* what the stage the item waits on landed without; the user brings it by
   hand: `handoff` in the composer for the report, the callouts ask for the
   callouts, the advance button for the handoff */
const OWES_HOW = {report:"send `handoff` to the session, or a comment that continues its pass",
                  callouts:"send `callouts` to the session",
                  handoff:"press advance"};
export function OwesBadge({x}){
  if(!x.owes) return null;
  return html`<span class="badge-owes" title=${"the stage landed without its "+x.owes+" — "+OWES_HOW[x.owes]}>${"owes "+x.owes}</span>`;
}
export function StateChip({state, label}){
  return html`<span class=${"chip "+CHIPCLS[state]}><span class="dot"></span>${label!==undefined?label:state}</span>`;
}
