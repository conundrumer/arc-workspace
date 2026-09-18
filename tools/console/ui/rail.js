/* The rail frame on the left: the sections a lens gives it, each a head,
   optional ordering tools, its rows, and a "show all" when the rows are
   cut. The two row kinds: a live item, and an unfinalized solver's row. */
import { html } from "/vendor/htm-preact-standalone.module.js";
import { useClock } from "/ui/clock.js";
import { cacheInfo } from "/ui/item.js";
import { CompBadges, CalloutBadge, NeedBadges, OwesBadge, StateChip } from "/ui/panels/badges.js";
import { Thumb } from "/ui/panels/grid.js";

export const passLabel = b => (b.passes||[]).map(p=>p.model).join(" ");

/* `row` is the lens row of the item's solver, given in the finalize lens,
   whose badges are the solver's review needs and whose sub line is the
   solver's rule-literal count, the number the lens orders on */
export function ItemRow({it, sel, task, metric, row, priority, onSelect}){
  useClock();   // the cache countdown
  const ci=cacheInfo(it);
  const sub = row ? "dl "+(row.dl_size ?? "—") : it.est ? "est "+it.est : "";
  return html`<div class=${"row"+(sel?" sel":"")} tabIndex="0"
      onClick=${()=>onSelect(it.id)}
      onKeyDown=${e=>{ if(e.key==="Enter") onSelect(it.id); }}>
    <${Thumb} task=${task}/>
    <div class="meta">
      <div class="tid">
        ${it.id}${" "}
        ${it.updated && html`<span class="badge-upd">UPD</span>`}
        <${OwesBadge} x=${it}/>
        ${it.dirty && html`<span class="badge-dirty">CLEANUP</span>`}
        ${row ? html`<${NeedBadges} x=${row} priority=${priority}/>`
              : html`<${CompBadges} x=${it}/><${CalloutBadge} x=${it}/>`}
      </div>
      <div class="sub">${sub}</div>
    </div>
    <div class="side">
      <${StateChip} state=${it.state} label=${it.state==="needs-review"?"review":it.state}/>
      <span class=${"ttl "+ci.cls}>${ci.txt}</span>
      <span class=${"phz"+(it.phase==="finalize"?" fin":"")}>${it.phase}</span>
      ${metric!=null && html`<span class="bksz mono">${metric}</span>`}
    </div>
  </div>`;
}

/* a solver's row: the needs it holds, the models of its passes, and the
   ruling where the user has made one */
export function BkRow({b, sel, task, metric, priority, onSelect}){
  return html`<div class=${"row bk"+(sel?" sel":"")} tabIndex="0"
      onClick=${()=>onSelect(b.id)}
      onKeyDown=${e=>{ if(e.key==="Enter") onSelect(b.id); }}>
    <${Thumb} task=${task}/>
    <div class="meta">
      <div class="tid">
        ${b.id}${" "}
        ${b.no_solver && html`<span class="badge-none"
          title="the pass wrote no solver">no solver</span>`}
        <${NeedBadges} x=${b} priority=${priority}/>
      </div>
      <div class="sub mono" title=${(b.passes||[]).map(p=>p.stage+": "+p.model).join("\n")}>${passLabel(b)}</div>
    </div>
    ${(b.ruling || metric!=null) && html`<div class="side">
      ${b.ruling && html`<${StateChip} state=${b.ruling==="approved"?"approved":"committed"}
        label=${b.ruling}/>`}
      ${metric!=null && html`<span class="bksz mono">${metric}</span>`}
    </div>`}
  </div>`;
}

/* a section: {key, head, rows, total, more, onMore}; rows are rendered
   already, total is how many there are when the rows on show are a cut, and
   `more` names the button that lifts the cut where "show all" does not read.
   The search box narrows every section to the ids holding its text, and
   lifts their cuts. `tools` are the lens controls, which stand over every
   section. */
export function Rail({sections, tools, filter, setFilter}){
  return html`<nav id="rail" aria-label="wave items">
    <input class="railsearch" type="search" placeholder="search ids" aria-label="search ids"
      value=${filter} onInput=${e=>setFilter(e.target.value.trim().toLowerCase())}/>
    ${tools||null}
    ${sections.map(s=>[
      html`<div class="railhead" key=${s.key+":head"}><span>${s.head}</span></div>`,
      ...s.rows,
      s.total>s.rows.length && html`<button class="bkmore" key=${s.key+":more"} onClick=${s.onMore}>
        ${s.more || "show all "+s.total}</button>`,
    ])}
  </nav>`;
}
