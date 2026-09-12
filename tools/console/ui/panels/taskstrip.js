/* The task strip over the code column: the train and test pairs of the
   item's task, and of each task the session's feed mentions, one tab per
   task. A pair's alt output, where the task has one, stands beside the
   output under its kind. */
import { html, useState, useEffect, useMemo } from "/vendor/htm-preact-standalone.module.js";
import { Grid } from "/ui/panels/grid.js";
import { tasks, ensureTask } from "/ui/server.js";

const loaded = t => !!t && typeof t!=="string";

function Pairs({task}){
  return html`<div class="gridwell"><div class="pairrow">
    ${task.train.map((p,i)=>html`<div class="pair" key=${"tr"+i}>
      <${Grid} g=${p.input} label=${"train "+i}/>
      <span class="arr">→</span>
      <${Grid} g=${p.output} label="out"/>
      ${p.alt && [html`<span class="arr" key="a">|</span>`,
                  html`<${Grid} key="g" g=${p.alt.grid} label=${"alt · "+p.alt.kind}/>`]}
    </div>`)}
    ${task.test.map((p,i)=>html`<div class="pair" key=${"te"+i}>
      <${Grid} g=${p.input} label=${"test "+i}/>
      ${p.output && [html`<span class="arr" key="a">→</span>`,
                     html`<${Grid} key="g" g=${p.output} label="expected"/>`]}
      ${p.alt && [html`<span class="arr" key="b">|</span>`,
                  html`<${Grid} key="h" g=${p.alt.grid} label=${"alt · "+p.alt.kind}/>`]}
    </div>`)}
  </div></div>`;
}

/* id: the item's own task, the first tab. mentions: the other ids the feed
   names; a mention is a tab once its task has loaded, so a hex word that is
   no task gets none. */
export function TaskStrip({id, mentions, open, onToggle}){
  const [tab,setTab]=useState(null);   // the id in view, null for the item's own
  useEffect(()=>{ setTab(null); },[id]);
  useEffect(()=>{ for(const m of mentions||[]) ensureTask(m); },[mentions]);
  const tabs = [id, ...(mentions||[]).filter(m=>m!==id && loaded(tasks[m]))].filter(Boolean);
  const cur = tab && tabs.includes(tab) ? tab : id;
  const task = cur ? tasks[cur] : null;
  const body = useMemo(()=>loaded(task) ? html`<${Pairs} task=${task}/>` : null, [task, cur]);
  return html`<div id="taskstrip" class=${open?"open":""}>
    <div class="taskhead" onClick=${onToggle}>
      <span class="caret">▸</span><span>task</span>
      ${tabs.length>1 && html`<span class="ttabs" onClick=${e=>e.stopPropagation()}>
        ${tabs.map(t=>html`<span key=${t} class=${"ttab"+(t===cur?" on":"")}
          onClick=${()=>setTab(t===id ? null : t)}>${t}</span>`)}
      </span>`}
      <span style="margin-left:auto">t</span>
    </div>
    <div id="taskbody">${body}</div>
  </div>`;
}
