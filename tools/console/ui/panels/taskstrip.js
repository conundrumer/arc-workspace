/* The task strip over the code column: the train and test pairs of the
   item's task, and of each task the session's feed mentions, one tab per
   task. A pair's alt output, where the task has one, stands beside the
   output under its kind. A task with a witness file gets one more tab: each
   entry's input beside the outcome it pins on every case, with the models
   that input separates and the fields of the solver's `@witness` block for
   that entry. */
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

const WIT = "witnesses";

/* A witness entry's outcomes as a per-case map: a bare grid is the judged
   output every case must differ from, keyed by the word for that; null is
   an undefined outcome. */
function outcomes(w){
  return Array.isArray(w.output) ? [["rejected", w.output]] : Object.entries(w.output);
}
/* the mark between the input and the outcomes: the cases give theirs on it,
   or, for a judged output, no case may give it */
const markOf = w => Array.isArray(w.output) ? "≠" : "→";

/* The lines a `@witness` block adds under the model: the plausibility and
   the verdict on one line, then a line per field that holds a slug or
   slugs. A field the block leaves empty draws nothing. */
function blockLines(w){
  const head = [w.plausibility, w.verdict].filter(Boolean).join(" · ");
  return [head,
          w.approximates ? "approximates: " + w.approximates : "",
          w.relaxed?.length ? "relaxed: " + w.relaxed.join(", ") : "",
          w.reassigned?.length ? "reassigned: " + w.reassigned.join(", ") : ""
         ].filter(Boolean);
}

/* Every outcome is what one case gives on the one input, so the mark stands
   between the input and the outcomes, once: the outcomes are siblings, and
   an arrow between them would read as a chain. */
function Witness({w}){
  const label = w.id + (w.assign ? " [" + Object.keys(w.assign).join(", ") + "]" : "");
  return html`<div class="wit">
    ${w.input
      ? html`<div class="pair">
          <${Grid} g=${w.input} label=${label}/>
          <span class="arr">${markOf(w)}</span>
          <div class="outs">
            ${outcomes(w).map(([c,g])=>
              g ? html`<${Grid} key=${c} g=${g} label=${c}/>`
                : html`<div class="gwrap" key=${c}><div class="glabel">${c}</div>
                         <div class="undef">undefined</div></div>`)}
          </div>
        </div>`
      : html`<div class="gwrap"><div class="glabel">${w.id}</div>
               <div class="undef">no entry</div></div>`}
    <div class="witprose">
      ${w.separates && html`<div>${w.separates}</div>`}
      ${blockLines(w).map(line=>html`<div class="witblock" key=${line}>${line}</div>`)}
    </div>
  </div>`;
}

function Witnesses({witness}){
  if(witness.error) return html`<div class="gridwell witerr">${witness.error}</div>`;
  return html`<div class="gridwell witlist">
    ${witness.entries.map(w=>html`<${Witness} key=${w.id} w=${w}/>`)}
  </div>`;
}

/* id: the item's own task, the first tab. mentions: the other ids the feed
   names; a mention is a tab once its task has loaded, so a hex word that is
   no task gets none. */
export function TaskStrip({id, mentions, witness, open, onToggle}){
  const [tab,setTab]=useState(null);   // the tab in view, null for the item's own task
  useEffect(()=>{ setTab(null); },[id]);
  useEffect(()=>{ for(const m of mentions||[]) ensureTask(m); },[mentions]);
  const tabs = [id, ...(mentions||[]).filter(m=>m!==id && loaded(tasks[m])),
                ...(witness ? [WIT] : [])].filter(Boolean);
  const cur = tab && tabs.includes(tab) ? tab : id;
  const task = cur===WIT ? null : cur ? tasks[cur] : null;
  const body = useMemo(()=>cur===WIT ? html`<${Witnesses} witness=${witness}/>`
    : loaded(task) ? html`<${Pairs} task=${task}/>` : null, [task, cur, witness]);
  return html`<div id="taskstrip" class=${open?"open":""}>
    <div class="taskhead">
      ${/* the pane opens and closes from this button alone; the rest of the
            head carries the tabs, and a click beside one is no toggle */
        html`<button class="tasktog" onClick=${onToggle}
          title="open or close the task pane · t">
          <span class="caret">▸</span><span>task</span></button>`}
      ${tabs.length>1 && html`<span class="ttabs">
        ${tabs.map(t=>html`<span key=${t} class=${"ttab"+(t===cur?" on":"")}
          onClick=${()=>setTab(t===id ? null : t)}>${t}</span>`)}
      </span>`}
      <span style="margin-left:auto">t</span>
    </div>
    <div id="taskbody">${body}</div>
  </div>`;
}
