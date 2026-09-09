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
