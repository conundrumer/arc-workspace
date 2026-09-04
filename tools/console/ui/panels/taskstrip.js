/* The task strip over the code column: the train and test pairs. */
import { html, useMemo } from "/vendor/htm-preact-standalone.module.js";
import { Grid } from "/ui/panels/grid.js";

export function TaskStrip({id, task, open, onToggle}){
  const body = useMemo(()=>{
    if(!task || typeof task==="string") return null;
    return html`<div class="gridwell"><div class="pairrow">
      ${task.train.map((p,i)=>html`<div class="pair" key=${"tr"+i}>
        <${Grid} g=${p.input} label=${"train "+i}/>
        <span class="arr">→</span>
        <${Grid} g=${p.output} label="out"/>
      </div>`)}
      ${task.test.map((p,i)=>html`<div class="pair" key=${"te"+i}>
        <${Grid} g=${p.input} label=${"test "+i}/>
        ${p.output && [html`<span class="arr" key="a">→</span>`,
                       html`<${Grid} key="g" g=${p.output} label="expected"/>`]}
      </div>`)}
    </div></div>`;
  },[task, id]);
  const label = task && typeof task!=="string"
    ? "task · "+task.train.length+" train / "+task.test.length+" test" : "task";
  return html`<div id="taskstrip" class=${open?"open":""}>
    <div class="taskhead" onClick=${onToggle}>
      <span class="caret">▸</span><span>${label}</span><span style="margin-left:auto">t</span>
    </div>
    <div id="taskbody">${body}</div>
  </div>`;
}
