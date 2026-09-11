/* The rail frame on the left: the sections a lens gives it, each a head,
   optional ordering tools, its rows, and a "show all" when the rows are
   cut. The two row kinds: a live item, and an unfinalized solver's row. */
import { html } from "/vendor/htm-preact-standalone.module.js";
import { useClock } from "/ui/clock.js";
import { cacheInfo } from "/ui/item.js";
import { CompBadges, CalloutBadge, OwesBadge, StateChip } from "/ui/panels/badges.js";
import { Thumb } from "/ui/panels/grid.js";

export const passLabel = b => (b.passes||[]).map(p=>p.model).join(" ");

export function ItemRow({it, sel, task, metric, onSelect}){
  useClock();   // the cache countdown
  const ci=cacheInfo(it);
  const sub = it.est ? "est "+it.est : "";
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
        <${CompBadges} x=${it}/><${CalloutBadge} x=${it}/>
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

export function BkRow({b, sel, task, metric, onSelect}){
  return html`<div class=${"row bk"+(sel?" sel":"")} tabIndex="0"
      onClick=${()=>onSelect(b.id)}
      onKeyDown=${e=>{ if(e.key==="Enter") onSelect(b.id); }}>
    <${Thumb} task=${task}/>
    <div class="meta">
      <div class="tid">
        ${b.id}${" "}
        ${b.no_solver && html`<span class="badge-none"
          title="the pass wrote no solver">no solver</span>`}
        <${CompBadges} x=${b}/><${CalloutBadge} x=${b}/>
      </div>
      <div class="sub mono" title=${(b.passes||[]).map(p=>p.stage+": "+p.model).join("\n")}>${passLabel(b)}</div>
    </div>
    ${metric!=null && html`<div class="side"><span class="bksz mono">${metric}</span></div>`}
  </div>`;
}

/* a section: {key, head, tools, rows, total, onMore}; rows are rendered
   already, total is how many there are when the rows on show are a cut.
   The search box narrows every section to the ids holding its text, and
   lifts their cuts. */
export function Rail({sections, filter, setFilter}){
  return html`<nav id="rail" aria-label="wave items">
    <input class="railsearch" type="search" placeholder="search ids" aria-label="search ids"
      value=${filter} onInput=${e=>setFilter(e.target.value.trim().toLowerCase())}/>
    ${sections.map(s=>[
      html`<div class="railhead" key=${s.key+":head"}><span>${s.head}</span>${s.tools||null}</div>`,
      ...s.rows,
      s.total>s.rows.length && html`<button class="bkmore" key=${s.key+":more"} onClick=${s.onMore}>
        ${"show all "+s.total}</button>`,
    ])}
  </nav>`;
}
