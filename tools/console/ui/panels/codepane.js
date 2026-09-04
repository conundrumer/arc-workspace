/* The code pane: the file in view with this turn's edits marked. */
import { html, useLayoutEffect, useRef } from "/vendor/htm-preact-standalone.module.js";

export function CodePane({jumpKey, fname, lines, buttons, pane}){
  const pre=useRef(null);
  /* A long file's edits are rarely at the top, so bring the first marked line
     into view. Only when the pane switches to a different file: re-running this
     as a turn streams would drag the pane away from whoever is reading it. */
  useLayoutEffect(()=>{
    const el=pre.current;
    if(!el) return;
    const first=el.querySelector(".add, .del");
    if(!first){ el.scrollTop=0; return; }
    const lead=(parseFloat(getComputedStyle(el).lineHeight)||0)*3;   // lines of lead-in
    el.scrollTop += first.getBoundingClientRect().top - el.getBoundingClientRect().top - lead;
  },[jumpKey]);
  return [
    html`<div class="codehead" key="h">
      <span class="fname">${fname}</span>
      <span id="flines">${lines}</span>
      <span id="codebtns" style="margin-left:auto">${buttons}</span>
    </div>`,
    html`<pre id="codepre" key="p" ref=${pre} dangerouslySetInnerHTML=${{__html:pane}}></pre>`,
  ];
}
