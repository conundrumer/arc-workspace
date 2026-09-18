/* The finalize lens: the items in a finalize pass, then every unfinalized
   solver on disk, in one of the lens orderings; a row peeks at the solver
   and its reports, and takes the ruling that ends it. Under those, the
   solvers already ruled on, newest first, so a ruling can be read again and
   a fresh pass started over it. */
import { html, useState, useEffect, useMemo, useCallback, useRef } from "/vendor/htm-preact-standalone.module.js";
import { useClocked } from "/ui/clock.js";
import { FINAL, SETTLED, cacheInfo } from "/ui/item.js";
import { PeekHead, PeekBody } from "/ui/panels/detail.js";
import { esc } from "/ui/prose.js";
import { ItemRow, BkRow, passLabel } from "/ui/rail.js";
import { snap as snapNow, tasks, peeks, post, ensureTask, ensureItem, ensurePeek } from "/ui/server.js";
import { useSession } from "/ui/session.js";
import { toast } from "/ui/toast.js";

/* The priority: the kind of review need that leads. The server holds it, and
   it also picks which badge a row leads with. The autopilot's finalize passes
   take the same order. */
const PRIORITY = {principle:"the rows waiting on a rule or open question first, the widest first and one key's rows together",
                  proposal:"the rows with a proposal comp first, the most callers first and one comp's rows together",
                  workaround:"the rows with a workaround first, most first",
                  sweep:"the rows with a sweep first, most first",
                  cite:"the rows with a cite first, most first"};
const PRIORITY_KINDS = Object.keys(PRIORITY);
/* The sort: the priority's review order as the server sent it, a grouping by
   the models of the passes, or a complexity measure. One choice sorts both
   sections; in the finalizing section it sorts the cold sessions, behind the
   warm ones. */
const SORTS = {review:"the priority's review order",
               passes:"grouped by the models of the passes, review order within",
               dl:"solver rule-literal count"};
const BK_SHOWN = 40;   // unfinalized rows listed until the user asks for the rest
/* The ruled rows are the solvers behind us, hundreds of them, so the section
   opens on the user's ask and is remembered open. */
const RULED_OPEN = "ruledOpen";
/* the chosen sort over lens rows; the review rank is the row's place in the
   server's list, and a task with no row goes last */
const rank = r => r.rank ?? Infinity;
const sortCmp = sort => (a,b) => {
  if(sort==="review") return rank(a)-rank(b) || 0;
  if(sort==="passes") return passLabel(a).localeCompare(passLabel(b)) || rank(a)-rank(b) || 0;
  const k=sort+"_size", av=a[k]??-1, bv=b[k]??-1;
  return bv-av || (a.id<b.id?-1:1);
};
const sizeOf = (row, sort) => sort==="dl" ? (row.dl_size ?? "—") : null;

export const finalize = {
  id: FINAL,
  use({snap, selId, setSelId, pins, cli, filter}){
    const items=snap.items;
    const [backlog,setBacklog]=useState([]);
    const [finRows,setFinRows]=useState({});   // id -> lens row of a finalize pass in flight
    const [bkAll,setBkAll]=useState(false);   // every unfinalized row, on the user's ask
    const [ruled,setRuled]=useState([]);      // the ruled solvers, newest first
    const [ruledShown,setRuledShown]=useState(()=>localStorage.getItem(RULED_OPEN)?BK_SHOWN:0);
    /* Until both scans have landed there is nothing to hold a selection
       against, so an id the page opened on is kept as it stands. */
    const [bkScanned,setBkScanned]=useState(false);
    const [ruledScanned,setRuledScanned]=useState(false);
    const scanned=bkScanned && ruledScanned;
    /* The priority is the server's, and the page follows it. The kind the
       user just picked stands in until a snapshot carries it, so the control
       answers the click at once. */
    const [picked,setPicked]=useState(null);
    const priority=picked||snap.priority||PRIORITY_KINDS[0];
    useEffect(()=>{ if(picked && snap.priority===picked) setPicked(null); },[snap.priority]);
    const [sort,setSort]=useState(()=>{
      const v=localStorage.getItem("bkSort");
      return Object.hasOwn(SORTS, v||"") ? v : "review";
    });
    const chooseSort=useCallback(v=>{
      localStorage.setItem("bkSort", v);
      setSort(v);
    },[]);

    const open=useRef(true);
    useEffect(()=>()=>{ open.current=false; },[]);
    const fetchBacklog=useCallback(async()=>{
      try {
        const r=await fetch("/api/backlog");
        const d=await r.json();
        if(!open.current) return;
        const ranked = rows => (rows||[]).map((row,i)=>({...row, rank:i}));
        setBacklog(ranked(d.items));
        setFinRows(Object.fromEntries(ranked(d.finalizing).map(row=>[row.id,row])));
        setBkScanned(true);
      } catch(e){}
    },[]);
    /* The ruled rows change only when the user rules, so they are taken once
       and again after a ruling, not on the poll. */
    const fetchRuled=useCallback(async()=>{
      try {
        const r=await fetch("/api/ruled");
        const d=await r.json();
        if(!open.current) return;
        setRuled((d||[]).map((row,i)=>({...row, rank:i})));
        setRuledScanned(true);
      } catch(e){}
    },[]);
    const afterRule=useCallback(()=>{ fetchBacklog(); fetchRuled(); },[fetchBacklog, fetchRuled]);
    /* the priority orders the rows the server sends, so the click that sets
       it takes the rows again */
    const choosePriority=useCallback(async v=>{
      setPicked(v);
      await post("/api/priority",{kind:v});
      fetchBacklog();
    },[fetchBacklog]);
    /* the scan stats every solver, so it is polled only while the lens is
       open, and slowly: a priority change and started passes refresh it on
       the spot */
    useEffect(()=>{
      fetchBacklog();
      fetchRuled();
      const h=setInterval(fetchBacklog, 15000);
      return ()=>clearInterval(h);
    },[fetchBacklog, fetchRuled]);
    /* a landing writes the ledger line the backlog reads, and a priority
       change reorders the rows */
    useEffect(()=>{ if(snap.seq) fetchBacklog(); },[snap.seq]);

    const railOrder=useClocked(()=>
      [...items].sort((a,b)=>cacheInfo(a).sort-cacheInfo(b).sort).map(it=>it.id),
      [items]);
    /* An approved or committed item is settled, so the lens gives its row
       back; the selected one stays, so a row does not vanish from under the
       detail pane while it is being read. A session with a cache to keep
       warm leads in cache order; the cold ones follow in the chosen
       ordering, over the rows the server sent for them. */
    const itemOrder=useClocked(()=>{
      const rows=railOrder.map(id=>items.find(x=>x.id===id)).filter(it=>
        it && it.phase===FINAL && (it.id===selId || !SETTLED.includes(it.state)));
      const cmp=sortCmp(sort), rowOf=it=>finRows[it.id]||{id:it.id};
      return rows.filter(it=>cacheInfo(it).cls!=="cold")
        .concat(rows.filter(it=>cacheInfo(it).cls==="cold").sort((a,b)=>cmp(rowOf(a), rowOf(b))))
        .map(it=>it.id);
    }, [railOrder, items, selId, sort, finRows]);
    /* the rows arrive in the priority's review order; the other sorts resort
       them here */
    const bkSorted=useMemo(()=>[...backlog].sort(sortCmp(sort)), [backlog, sort]);
    const bkShown=useMemo(()=>filter ? bkSorted.filter(b=>b.id.includes(filter))
      : bkAll ? bkSorted : bkSorted.slice(0, BK_SHOWN), [bkSorted, bkAll, filter]);
    const finShown=useMemo(()=>filter ? itemOrder.filter(id=>id.includes(filter)) : itemOrder,
      [itemOrder, filter]);
    /* the ruled rows arrive newest first, and the other sorts resort them */
    const ruledSorted=useMemo(()=>[...ruled].sort(sortCmp(sort)), [ruled, sort]);
    const ruledRows=useMemo(()=>filter ? ruledSorted.filter(b=>b.id.includes(filter))
      : ruledSorted.slice(0, ruledShown), [ruledSorted, ruledShown, filter]);
    /* one selection over the sections: in-pass items, the unfinalized rows on
       show, then the ruled ones. An id that is both a live item and a row
       resolves to the item, and an unfinalized row wins over a ruled one. */
    const order=useMemo(()=>{
      const seen=new Set(itemOrder);
      const out=finShown.concat(bkShown.map(b=>b.id).filter(id=>!seen.has(id)));
      for(const b of bkShown) seen.add(b.id);
      return out.concat(ruledRows.map(b=>b.id).filter(id=>!seen.has(id)));
    }, [finShown, bkShown, ruledRows, itemOrder]);

    const selItem = items.find(it=>it.id===selId) || null;
    /* the selected solver's row, whether it waits on a ruling or carries one */
    const selBk = !selItem ? (backlog.find(b=>b.id===selId)
      || ruled.find(b=>b.id===selId) || null) : null;
    const detailId = selItem ? selItem.id : selBk ? selBk.id : null;

    const select=useCallback(id=>{
      if(!id) return;
      setSelId(id);
      const it=snapNow().items.find(x=>x.id===id);
      ensureTask(id);
      if(it){
        ensureItem(id, true);
        if(it.updated) post("/api/seen",{id});
      } else {
        ensurePeek(id, true);
      }
    },[]);
    const session=useSession(selItem, {cli, reviewOrder:railOrder, select, pins, afterRule});
    const onApprove=useCallback(async id=>{
      if(!confirm("Approve "+id+"? The draft line comes off the solver file.")) return;
      await post("/api/approve-solver",{id});
      afterRule();
    },[afterRule]);
    /* a ruled solver is revisited by another pass over it, which starts here
       and lands as any finalize pass does */
    const onFinalize=useCallback(async id=>{
      if(!confirm("Start a finalize pass on "+id+"?")) return;
      const r=await post("/api/finalize",{id});
      if(r.ok){
        toast("finalize pass started · "+id);
        fetchBacklog();
      }
    },[fetchBacklog]);

    /* the rows on screen want their thumbnails */
    useEffect(()=>{ for(const id of order) ensureTask(id); },[order]);

    /* ---- the peeked solver ---- */
    const peek = selBk ? peeks[selBk.id] : null;
    const peekPane = useMemo(()=>peek?esc(peek.solver):"", [peek]);
    let head=session.head, body=session.body, code=session.code;
    if(selBk){
      head = peek ? html`<${PeekHead} d=${peek} ruling=${selBk.ruling}
        onDismiss=${session.dismiss} onApprove=${onApprove} onFinalize=${onFinalize}/>` : null;
      body = peek ? html`<${PeekBody} key="peek" d=${peek}/>`
                  : html`<div id="judge-scroll" key="peek"></div>`;
      code = peek ? {jumpKey:"peek|"+peek.id, fname:"programs/solvers/"+peek.id+".dl",
                     lines:peek.solver.split("\n").length+" lines", buttons:null, pane:peekPane}
                  : null;
    }

    /* how many rows on the lens, in a pass or unfinalized, hold a need of
       each kind, so a kind carries its count in the drop-down */
    const lensRows=useMemo(()=>itemOrder.map(id=>finRows[id]).filter(Boolean).concat(backlog),
      [itemOrder, finRows, backlog]);
    const needCounts=useMemo(()=>Object.fromEntries(PRIORITY_KINDS.map(k=>
      [k, lensRows.filter(b=>((b.needs||{})[k]||[]).length).length])), [lensRows]);
    /* the two controls over both sections: which kind of need leads, picked
       from a drop-down, and how the rows are sorted */
    const tools=html`<div class="railtools">
      <span class="railpick">
        <span class="lead">lead</span>
        <select aria-label="review priority" value=${priority}
          onChange=${e=>choosePriority(e.target.value)}>
          ${PRIORITY_KINDS.map(k=>html`<option key=${k} value=${k}
            title=${PRIORITY[k]}>${k+" "+needCounts[k]}</option>`)}
        </select>
      </span>
      <span class="bktog" role="group" aria-label="row sort">
        ${Object.keys(SORTS).map(k=>html`<button key=${k} class=${sort===k?"on":""}
          title=${SORTS[k]}
          onClick=${()=>chooseSort(k)}>${k==="dl"?"dl ↓":k}</button>`)}
      </span>
    </div>`;
    const finRowsShown=finShown.map(id=>html`<${ItemRow} key=${id} it=${items.find(x=>x.id===id)}
      task=${tasks[id]} row=${finRows[id]} priority=${priority}
      sel=${!!selItem && id===selId} onSelect=${select}/>`);
    /* the unfinalized and the ruled rows are the same row: what the solver
       is, and the ruling it carries where it has one */
    const solverRow = b=>html`<${BkRow} key=${b.id} b=${b} task=${tasks[b.id]}
      metric=${sizeOf(b, sort)} priority=${priority}
      sel=${b.id===selId && !itemOrder.includes(b.id)} onSelect=${select}/>`;
    const bkRows=bkShown.map(solverRow);
    const ruledShownRows=ruledRows.map(solverRow);
    /* the section opens on the first ask, and the rest of its rows come on
       the second */
    const moreRuled=useCallback(()=>setRuledShown(n=>{
      localStorage.setItem(RULED_OPEN, "1");
      return n ? Infinity : BK_SHOWN;
    }),[]);
    return {
      order,
      pick: id => id && (!scanned || items.some(x=>x.id===id)
        || backlog.some(b=>b.id===id) || ruled.some(b=>b.id===id))
        ? id : (order[0] || railOrder[0] || null),
      settle: id => { ensureTask(id); if(items.some(x=>x.id===id)) ensureItem(id); else ensurePeek(id); },
      select,
      detailId,
      tools,
      sections: [
        {key:"fin", head:"finalizing · "+itemOrder.length, rows:finRowsShown, total:finShown.length},
        {key:"bk", head:"unfinalized · "+bkSorted.length, rows:bkRows,
         total:filter ? bkRows.length : bkSorted.length, onMore:()=>setBkAll(true)},
        {key:"ruled", head:"ruled · "+ruledSorted.length, rows:ruledShownRows,
         total:filter ? ruledShownRows.length : ruledSorted.length,
         more: ruledShown ? null : "read the ruled solvers", onMore:moreRuled},
      ],
      mentions: session.mentions,
      head, body, composer: session.composer, code,
      keys: session.keys,
    };
  },
};
