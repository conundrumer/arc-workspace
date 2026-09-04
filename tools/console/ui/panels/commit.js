/* The committer panel. */
import { html, useEffect, useRef } from "/vendor/htm-preact-standalone.module.js";
import { feedBlocks, Entry, ToolLine } from "/ui/panels/feed.js";
import { hhmm } from "/ui/prose.js";

/* ---------- committer panel ----------
   What the committer session says and runs, as the server streams it. The
   feed stays up after the run, until the next commit starts one. */
export function CommitPanel({committer, open}){
  const c=committer||{}, box=useRef(null);
  useEffect(()=>{ if(box.current) box.current.scrollTop=box.current.scrollHeight; });
  const rows=feedBlocks(c.feed||[]).map(b=>b.tools
    ? html`<div class="tools" key=${b.key}>${b.tools.map((m,i)=>html`<${ToolLine} key=${i} m=${m}/>`)}</div>`
    : html`<${Entry} key=${b.key} m=${b.m}/>`);
  return html`<div id="commitpanel" hidden=${!open}>
    <div id="commitfeed" ref=${box}>
      ${rows}
      ${c.running ? html`<p class="placeholder"><span class="runpulse"></span>${
          "committer running"+(c.started?" · since "+hhmm(c.started):"")}</p>` : null}
    </div>
  </div>`;
}
