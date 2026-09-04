/* The session feed: what a worker says and runs, and the user's turns. */
import { html, useLayoutEffect, useRef, useMemo } from "/vendor/htm-preact-standalone.module.js";
import { useClock } from "/ui/clock.js";
import { fmtDur, md } from "/ui/prose.js";

/* ---------- feed ----------
   Entries are keyed by position, so a streaming turn appends and the rows
   already on screen stay put. Consecutive tool lines share one group. */
export function feedBlocks(entries){
  const out=[];
  entries.forEach((m,i)=>{
    if(m.kind==="tool"){
      const last=out[out.length-1];
      if(last && last.tools) last.tools.push(m);
      else out.push({key:i, tools:[m]});
    } else out.push({key:i, m});
  });
  return out;
}
export function Entry({m}){
  if(m.kind==="report")
    return html`<section class="report"><div class="body"
      dangerouslySetInnerHTML=${{__html:md(m.text)}}></div></section>`;
  if(m.kind==="event")
    return html`<div class="event">${"— "+m.text+" —"}</div>`;
  if(m.kind==="ask")
    return html`<div class="msg ask" dangerouslySetInnerHTML=${{__html:md(m.text)}}></div>`;
  const bubble = m.kind==="you" ? "you" : m.kind==="steer" ? "steer" : "worker";
  return html`<div class=${"msg "+bubble+(m.sub?" sub":"")}
    dangerouslySetInnerHTML=${{__html:md(m.text)}}></div>`;
}
export function ToolLine({m}){
  const sp=m.text.indexOf(" ");
  return html`<div class=${"tl"+(m.sub?" sub":"")}>${
    sp<0 ? html`<b>${m.text}</b>`
         : [html`<b key="h">${m.text.slice(0,sp)}</b>`, " "+m.text.slice(sp+1)]}</div>`;
}

export function Feed({it, entries, feedKey, showRun}){
  const box=useRef(null), stick=useRef(true), lastKey=useRef(null);
  useClock();   // the running-turn timer
  const now=Date.now()/1000;
  /* measured against the DOM as it stands before this render commits, the way
     a hand-written append would: at the bottom now means at the bottom after */
  if(lastKey.current!==feedKey) stick.current=true;
  else if(box.current){
    const js=box.current;
    stick.current = js.scrollHeight - js.scrollTop - js.clientHeight < 60;
  }
  useLayoutEffect(()=>{
    lastKey.current=feedKey;
    if(stick.current && box.current) box.current.scrollTop=box.current.scrollHeight;
  });
  const rows=useMemo(()=>feedBlocks(entries).map(b=>b.tools
    ? html`<div class="tools" key=${b.key}>${b.tools.map((m,i)=>html`<${ToolLine} key=${i} m=${m}/>`)}</div>`
    : html`<${Entry} key=${b.key} m=${b.m}/>`), [entries]);
  return html`<div id="judge-scroll" ref=${box}>
    <div id="feed" data-tid=${it.id}>
      ${rows}
      ${showRun
        ? html`<p class="placeholder"><span class="runpulse"></span>worker running${
            it.turnStarted ? html`<span> · <span>${fmtDur(now-it.turnStarted)}</span></span>` : ""}</p>`
        : !entries.length
        ? html`<p class="placeholder">${it.state==="queued"?"queued":"no messages yet"}</p>`
        : null}
    </div>
  </div>`;
}
